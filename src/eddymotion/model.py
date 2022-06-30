"""A factory class that adapts DIPY's dMRI models."""
import asyncio
import warnings
from concurrent.futures import ThreadPoolExecutor
from os import cpu_count

import nest_asyncio
import numpy as np
from dipy.core.gradients import check_multi_b, gradient_table

nest_asyncio.apply()


def get_run_cls(init_cls, omp_nthreads=None):
    omp_nthreads = omp_nthreads or cpu_count()
    if omp_nthreads > 1:
        init_cls._model = [init_cls._model] * omp_nthreads
        return _AsyncFitPredict(init_cls)
    return _SerialFitPredict(init_cls)


class _SerialFitPredict:
    """Base fit and predict methods for all models in eddymotion."""

    __slots__ = (
        "_model",
        "_mask",
        "_S0",
    )

    def __init__(self, init_cls):
        self._model = init_cls._model
        self._mask = init_cls._mask
        self._S0 = init_cls._S0

    def fit(self, data, **kwargs):
        """Clean-up permitted args and kwargs, and call model's fit."""
        self._model = self._model.fit(data[self._mask, ...])

    def predict(self, gradient, step=None, **kwargs):
        """Propagate model parameters and call predict."""
        predicted = np.squeeze(
            self._model.predict(
                _rasb2dipy(gradient),
                S0=self._S0,
            )
        )
        if predicted.ndim == 3:
            return predicted

        retval = np.zeros_like(self._mask, dtype="float32")
        retval[self._mask, ...] = predicted
        return retval


class _AsyncFitPredict:
    """Parallel Asynchronous fit and predict methods for all models in
    eddymotion."""

    __slots__ = (
        "_model",
        "_mask",
        "_S0",
    )

    def __init__(self, init_cls):
        self._model = init_cls._model
        self._mask = init_cls._mask
        self._S0 = init_cls._S0

    def fit(self, data, **kwargs):
        """Fit the model chunk-by-chunk asynchronously"""
        _nthreads = len(self._model)

        # All-true mask if not available
        if self._mask is None:
            self._mask = np.ones(data.shape[:3], dtype=bool)

        # Apply mask (ensures data is now 2D)
        data = data[self._mask, ...]

        # Split data into chunks of group of slices
        data_chunks = np.array_split(data, _nthreads)

        # Run asyncio tasks in a limited thread pool
        with ThreadPoolExecutor(max_workers=_nthreads) as executor:
            loop = asyncio.new_event_loop()

            fit_tasks = [
                loop.run_in_executor(
                    executor,
                    _model_fit,
                    model,
                    data,
                )
                for model, data in zip(self._model, data_chunks)
            ]

            try:
                self._model = loop.run_until_complete(asyncio.gather(*fit_tasks))
            finally:
                loop.close()

    @staticmethod
    def _predict_sub(submodel, gradient, S0_chunk, step):
        """Call predict for chunk and return the predicted diffusion signal."""
        return submodel.predict(gradient, S0=S0_chunk, step=step)

    def predict(self, gradient, step=None, **kwargs):
        """Predict asynchronously chunk-by-chunk the diffusion signal."""
        _nthreads = len(self._model)
        S0 = [None] * _nthreads
        if self._S0 is not None:
            S0 = np.array_split(self._S0, _nthreads)

        # Run asyncio tasks in a limited thread pool
        with ThreadPoolExecutor(max_workers=_nthreads) as executor:
            loop = asyncio.new_event_loop()

            predict_tasks = [
                loop.run_in_executor(
                    executor,
                    self._predict_sub,
                    model,
                    _rasb2dipy(gradient),
                    S0_chunk,
                    step,
                )
                for model, S0_chunk in zip(self._model, S0)
            ]

            try:
                predicted = loop.run_until_complete(asyncio.gather(*predict_tasks))
            finally:
                loop.close()

        predicted = np.squeeze(np.concatenate(predicted, axis=0))
        retval = np.zeros_like(self._mask, dtype="float32")
        retval[self._mask] = predicted
        return retval


class ModelFactory:
    """A factory for instantiating diffusion models."""

    @staticmethod
    def init(gtab, model="DTI", **kwargs):
        """
        Instatiate a diffusion model.

        Parameters
        ----------
        gtab : :obj:`numpy.ndarray`
            An array representing the gradient table in RAS+B format.
        model : :obj:`str`
            Diffusion model.
            Options: ``"3DShore"``, ``"SFM"``, ``"GP"``, ``"DTI"``,
            ``"DKI"``, ``"S0"``

        Return
        ------
        model : :obj:`~dipy.reconst.ReconstModel`
            An model object compliant with DIPY's interface.

        """
        if model.lower() in ("s0", "b0"):
            return TrivialB0Model(gtab=gtab, S0=kwargs.pop("S0"))

        if model.lower() in ("avg", "average", "mean"):
            return AverageDWModel(gtab=gtab, **kwargs)

        # Generate a GradientTable object for DIPY
        gtab = _rasb2dipy(gtab)
        param = {}

        if model.lower().startswith("3dshore"):
            from dipy.reconst.shore import ShoreModel as Model

            param = {
                "radial_order": 6,
                "zeta": 700,
                "lambdaN": 1e-8,
                "lambdaL": 1e-8,
            }

        elif model.lower() in ("sfm", "gp"):
            Model = SparseFascicleModel
            param = {"solver": "ElasticNet"}

            if model.lower() == "gp":
                from sklearn.gaussian_process import GaussianProcessRegressor

                param = {"solver": GaussianProcessRegressor}

            multi_b = check_multi_b(gtab, 2, non_zero=False)
            if multi_b:
                from dipy.reconst.sfm import ExponentialIsotropicModel

                param.update({"isotropic": ExponentialIsotropicModel})

        elif model.lower() in ("dti", "dki"):
            Model = DTIModel if model.lower() == "dti" else DKIModel

        else:
            raise NotImplementedError(f"Unsupported model <{model}>.")

        omp_nthreads = kwargs.pop("omp_nthreads", None)
        param.update(kwargs)
        return get_run_cls(Model(gtab, **param), omp_nthreads)


class TrivialB0Model:
    """
    A trivial model that returns a *b=0* map always.

    Implements the interface of :obj:`dipy.reconst.base.ReconstModel`.
    Instead of inheriting from the abstract base, this implementation
    follows type adaptation principles, as it is easier to maintain
    and to read (see https://www.youtube.com/watch?v=3MNVP9-hglc).

    """

    __slots__ = ("_S0",)

    def __init__(self, gtab, S0=None, **kwargs):
        """Implement object initialization."""
        if S0 is None:
            raise ValueError("S0 must be provided")

        self._S0 = S0

    def fit(self, *args, **kwargs):
        """Do nothing."""

    def predict(self, gradient, **kwargs):
        """Return the *b=0* map."""
        return self._S0


class AverageDWModel:
    """A trivial model that returns an average map."""

    __slots__ = ("_data", "_gtab", "_th_low", "_th_high", "_bias", "_stat")

    def __init__(self, gtab, **kwargs):
        r"""
        Implement object initialization.

        Parameters
        ----------
        gtab : :obj:`~numpy.ndarray`
            An :math:`N \times 4` table, where rows (*N*) are diffusion gradients and
            columns are b-vector components and corresponding b-value, respectively.
        th_low : :obj:`~numbers.Number`
            A lower bound for the b-value corresponding to the diffusion weighted images
            that will be averaged.
        th_high : :obj:`~numbers.Number`
            An upper bound for the b-value corresponding to the diffusion weighted images
            that will be averaged.
        bias : :obj:`bool`
            Whether the overall distribution of each diffusion weighted image will be
            standardized and centered around the global 75th percentile.
        stat : :obj:`str`
            Whether the summary statistic to apply is ``"mean"`` or ``"median"``.

        """
        self._gtab = gtab
        self._th_low = kwargs.get("th_low", 50)
        self._th_high = kwargs.get("th_high", self._gtab[3, ...].max())
        self._bias = kwargs.get("bias", True)
        self._stat = kwargs.get("stat", "median")

    def fit(self, data, **kwargs):
        """Calculate the average."""
        # Select the interval of b-values for which DWIs will be averaged
        b_mask = (self._gtab[3, ...] >= self._th_low) & (
            self._gtab[3, ...] <= self._th_high
        )
        shells = data[..., b_mask]

        # Regress out global signal differences
        if self._bias:
            centers = np.median(shells, axis=(0, 1, 2))
            reference = np.percentile(centers[centers >= 1.0], 75)
            centers[centers < 1.0] = reference
            drift = reference / centers
            shells = shells * drift

        # Select the summary statistic
        avg_func = np.median if self._stat == "median" else np.mean
        # Calculate the average
        self._data = avg_func(shells, axis=-1)

    def predict(self, gradient, **kwargs):
        """Return the average map."""
        return self._data


class PETUptakeModel:
    """A trivial model of PET radiotracer uptake."""

    __slots__ = ("_data", "_uptake")

    def __init__(self, data, **kwargs):
        r"""
        Implement object initialization.

        Parameters
        ----------
        data : :obj:`~numpy.ndarray`
            The original 3D timeseries from which a "canonical" uptake function will be
            estimated.


        """

    def fit(self, data, **kwargs):
        """Impute the missing volume from the remainder of the dataset."""
        # self._data =

    def predict(self, gradient, **kwargs):
        """Return the modeled frame."""
        return self._data


class DTIModel:
    """A wrapper of :obj:`dipy.reconst.dti.TensorModel."""

    __slots__ = ("_model", "_S0", "_mask")

    def __init__(self, gtab, S0=None, mask=None, **kwargs):
        """Instantiate the wrapped tensor model."""
        from dipy.reconst.dti import TensorModel as DipyTensorModel

        self._S0 = None

        if S0 is not None:
            self._S0 = np.clip(
                S0.astype("float32") / S0.max(),
                a_min=1e-5,
                a_max=1.0,
            )

        self._mask = mask > 0 if mask is not None else None
        if self._mask is None and self._S0 is not None:
            self._mask = self._S0 > np.percentile(self._S0, 35)

        if self._S0 is not None:
            self._S0 = self._S0[self._mask]

        kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in (
                "min_signal",
                "return_S0_hat",
                "fit_method",
                "weighting",
                "sigma",
                "jac",
            )
        }

        self._model = DipyTensorModel(gtab, **kwargs)


class DKIModel:
    """A wrapper of :obj:`dipy.reconst.dki.DiffusionKurtosisModel."""

    __slots__ = ("_model", "_S0", "_mask")

    def __init__(self, gtab, S0=None, mask=None, **kwargs):
        """Instantiate the wrapped tensor model."""
        from dipy.reconst.dki import DiffusionKurtosisModel

        self._S0 = None
        if S0 is not None:
            self._S0 = np.clip(
                S0.astype("float32") / S0.max(),
                a_min=1e-5,
                a_max=1.0,
            )
        self._mask = mask
        if mask is None and S0 is not None:
            self._mask = self._S0 > np.percentile(self._S0, 35)

        if self._mask is not None:
            self._S0 = self._S0[self._mask.astype(bool)]

        kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in (
                "min_signal",
                "return_S0_hat",
                "fit_method",
                "weighting",
                "sigma",
                "jac",
            )
        }

        self._model = DiffusionKurtosisModel(gtab, **kwargs)


class SparseFascicleModel:
    """
    A wrapper of :obj:`dipy.reconst.sfm.SparseFascicleModel.
    """

    __slots__ = ("_model", "_parallel", "_S0", "_mask", "_solver")

    def __init__(self, gtab, S0=None, mask=None, solver=None, **kwargs):
        """Instantiate the wrapped model."""
        from dipy.reconst.sfm import SparseFascicleModel

        self._S0 = None
        if S0 is not None:
            self._S0 = np.clip(
                S0.astype("float32") / S0.max(),
                a_min=1e-5,
                a_max=1.0,
            )

        self._mask = mask
        if mask is None and S0 is not None:
            self._mask = self._S0 > np.percentile(self._S0, 35)

        if self._mask is not None:
            self._S0 = self._S0[self._mask.astype(bool)]

        self._solver = solver
        if solver is None:
            self._solver = "ElasticNet"

        kwargs = {k: v for k, v in kwargs.items() if k in ("solver",)}

        self._model = SparseFascicleModel(gtab, **kwargs)


def _rasb2dipy(gradient):
    gradient = np.asanyarray(gradient)
    if gradient.ndim == 1:
        if gradient.size != 4:
            raise ValueError("Missing gradient information.")
        gradient = gradient[..., np.newaxis]

    if gradient.shape[0] != 4:
        gradient = gradient.T
    elif gradient.shape == (4, 4):
        print("Warning: make sure gradient information is not transposed!")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        retval = gradient_table(gradient[3, :], gradient[:3, :].T)
    return retval


def _model_fit(model, data):
    return model.fit(data)
