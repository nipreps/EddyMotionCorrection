# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2022 The NiPreps Developers <nipreps@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# We support and encourage derived works from this project, please read
# about our expectations at
#
#     https://www.nipreps.org/community/licensing/
#
"""A model-based algorithm for the realignment of dMRI data."""
import gc
from pathlib import Path
from tempfile import TemporaryDirectory, mkstemp
from dataclasses import dataclass
from typing import Optional, Dict, Union, List, Tuple

import nibabel as nb
import nitransforms as nt
import numpy as np

from nipype.interfaces.ants.registration import Registration
from pkg_resources import resource_filename as pkg_fn
from tqdm import tqdm

from eddymotion.model import ModelFactory
from eddymotion.data.dmri import DWI


class EddyMotionEstimator:
    """Estimates rigid-body head-motion and distortions derived from eddy-currents."""

    @staticmethod
    def fit(
        dwdata,
        *,
        align_kwargs=None,
        models=("b0",),
        omp_nthreads=None,
        n_jobs=None,
        seed=None,
        **kwargs,
    ):
        r"""
        Estimate head-motion and Eddy currents.

        Parameters
        ----------
        dwdata : :obj:`~eddymotion.dmri.DWI`
            The target DWI dataset, represented by this tool's internal
            type. The object is used in-place, and will contain the estimated
            parameters in its ``em_affines`` property, as well as the rotated
            *b*-vectors within its ``gradients`` property.
        n_iter : :obj:`int`
            Number of iterations this particular model is going to be repeated.
        align_kwargs : :obj:`dict`
            Parameters to configure the image registration process.
        model : :obj:`str`
            Selects the diffusion model that will generate the registration target
            corresponding to each gradient map.
            See :obj:`~eddymotion.model.ModelFactory` for allowed models (and corresponding
            keywords).
        seed : :obj:`int` or :obj:`bool`
            Seed the random number generator (necessary when we want deterministic
            estimation).

        Return
        ------
        affines : :obj:`list` of :obj:`numpy.ndarray`
            A list of :math:`4 \times 4` affine matrices encoding the estimated
            parameters of the deformations caused by head-motion and eddy-currents.

        """
        align_kwargs = align_kwargs or {}

        if seed or seed == 0:
            np.random.seed(20210324 if seed is True else seed)

        bmask_img = None
        if dwdata.brainmask is not None:
            _, bmask_img = mkstemp(suffix="_bmask.nii.gz")
            nb.Nifti1Image(dwdata.brainmask.astype("uint8"), dwdata.affine, None).to_filename(
                bmask_img
            )
            kwargs["mask"] = dwdata.brainmask

        kwargs["S0"] = _advanced_clip(dwdata.bzero)

        if "num_threads" not in align_kwargs and omp_nthreads is not None:
            align_kwargs["num_threads"] = omp_nthreads

        aligner = Aligner(dwdata, bmask_img, align_kwargs, models)

        n_iter = len(models)
        for i_iter, model in enumerate(models):
            index_order = np.arange(len(dwdata))
            np.random.shuffle(index_order)

            aligner.set_model_iter(i_iter)

            single_model = model.lower() in (
                "b0",
                "s0",
                "avg",
                "average",
                "mean",
            ) or model.lower().startswith("full")

            dwmodel = None
            if single_model:
                if model.lower().startswith("full"):
                    model = model[4:]

                # Factory creates the appropriate model and pipes arguments
                dwmodel = ModelFactory.init(
                    gtab=dwdata.gradients,
                    model=model,
                    **kwargs,
                )
                dwmodel.fit(dwdata.dataobj, n_jobs=n_jobs)

            with TemporaryDirectory() as tmpdir:
                print(f"Processing in <{tmpdir}>")

                with tqdm(total=len(index_order), unit="dwi") as pbar:
                    # run a original-to-synthetic affine registration
                    for b_ix in index_order:
                        pbar.set_description_str(
                            f"Pass {i_iter + 1}/{n_iter} | Fit and predict b-index <{b_ix}>"
                        )
                        data_train, data_test = dwdata.logo_split(b_ix, with_b0=True)
                        grad_str = f"{b_ix}, {data_test[1][:3]}, b={int(data_test[1][3])}"
                        pbar.set_description_str(f"[{grad_str}], {n_jobs} jobs")

                        if not single_model:  # A true LOGO estimator
                            # Factory creates the appropriate model and pipes arguments
                            dwmodel = ModelFactory.init(
                                gtab=data_train[1],
                                model=model,
                                n_jobs=n_jobs,
                                **kwargs,
                            )

                            # fit the model
                            dwmodel.fit(
                                data_train[0],
                                n_jobs=n_jobs,
                            )

                        # predict the gradient
                        predicted = dwmodel.predict(data_test[1])
                        pbar.set_description_str(
                            f"Pass {i_iter + 1}/{n_iter} | Realign b-index <{b_ix}>"
                        )

                        # Initialize the ANTs registration object for the current model iteration
                        xform = aligner.transform(Path(tmpdir), data_test, b_ix, predicted)

                        # update
                        dwdata.set_transform(b_ix, xform.matrix)
                        pbar.update()

                        # free memory
                        del xform, predicted, data_train, data_test
                        gc.collect()

        return dwdata.em_affines


@dataclass
class Aligner:
    """Convenience dataclass that wraps and tracks ANTs registrations for each gradient prediction.

    Attributes
    ----------
    dwdata : :obj:`~eddymotion.data.DWI`
        The DWI data object.
    bmask_img : :obj:`str`
        Path to a brain mask image.
    align_kwargs : :obj:`dict`
        Additional keyword arguments to pass to the ANTs registration call.
    models : :obj:`list` of :obj:`str`
        List of model names.

    """

    dwdata: DWI
    bmask_img: Optional[str]
    align_kwargs: Dict
    models: Union[List[str], Tuple[str]]

    def set_model_iter(self, i_iter: int) -> None:
        """Set the model iteration."""
        self._model_iter = i_iter

    @property
    def model(self) -> str:
        """Return the model name."""
        return self.models[self._model_iter]

    @property
    def reg_target_type(self) -> str:
        """Return the registration target type."""
        return (
            "dwi"
            if self.models[self._model_iter].lower() not in ("b0", "s0", "avg", "average", "mean")
            else "b0"
        )

    def transform(
        self, basedir: Path, data_test: np.ndarray, b_ix: int, predicted: np.ndarray
    ) -> nt.linear.Affine:
        """Run ANTs registration and return the resulting transform.

        Parameters
        ----------
        basedir : :obj:`pathlib.Path`
            Path to a working directory.
        data_test : :obj:`numpy.ndarray`
            The test data.
        b_ix : :obj:`int`
            The index of the current gradient.
        predicted : :obj:`numpy.ndarray`
            The predicted dw volume for the test gradient.

        """

        if self.bmask_img:
            self.registration.inputs.fixed_image_masks = ["NULL", self.bmask_img]

        # prepare data for running ANTs
        moving = basedir / f"moving{b_ix:05d}.nii.gz"
        fixed = basedir / f"fixed{b_ix:05d}.nii.gz"
        _to_nifti(data_test[0], self.dwdata.affine, moving)
        _to_nifti(
            predicted,  # generate a synthetic dw volume for the test gradient
            self.dwdata.affine,
            fixed,
            clip=self.reg_target_type == "dwi",
        )

        self.registration = Registration(
            terminal_output="file",
            from_file=pkg_fn(
                "eddymotion",
                f"config/dwi-to-{self.reg_target_type}_level{self._model_iter}.json",
            ),
            fixed_image=str(fixed.absolute()),
            moving_image=str(moving.absolute()),
            **self.align_kwargs,
        )

        if self.dwdata.em_affines and self.dwdata.em_affines[b_ix] is not None:
            mat_file = basedir / f"init_{self._model_iter}_{b_ix:05d}.mat"
            self.dwdata.em_affines[b_ix].to_filename(mat_file, fmt="itk")
            self.registration.inputs.initial_moving_transform = str(mat_file)

        # read output transform
        xform = nt.linear.Affine(
            nt.io.itk.ITKLinearTransform.from_filename(
                self.registration.run(cwd=str(basedir)).outputs.forward_transforms[0]
            ).to_ras(reference=fixed, moving=moving),
        )
        # debugging: generate aligned file for testing
        xform.apply(moving, reference=fixed).to_filename(
            basedir / f"aligned{b_ix:05d}_{int(data_test[1][3]):04d}.nii.gz"
        )

        return xform


def _advanced_clip(data, p_min=35, p_max=99.98, nonnegative=True, dtype="int16", invert=False):
    r"""
    Remove outliers at both ends of the intensity distribution and fit into a given dtype.

    This interface tries to emulate ANTs workflows' massaging that truncate images into
    the 0-255 range, and applies percentiles for clipping images.
    For image registration, normalizing the intensity into a compact range (e.g., uint8)
    is generally advised.

    To more robustly determine the clipping thresholds, spikes are removed from data with
    a median filter.
    Once the thresholds are calculated, the denoised data are thrown away and the thresholds
    are applied on the original image.

    """
    import numpy as np
    from scipy import ndimage
    from skimage.morphology import ball

    # Calculate stats on denoised version, to preempt outliers from biasing
    denoised = ndimage.median_filter(data, footprint=ball(3))

    if len(denoised[denoised > 0]) == 0:
        return data

    a_min = np.percentile(denoised[denoised > 0] if nonnegative else denoised, p_min)
    a_max = np.percentile(denoised[denoised > 0] if nonnegative else denoised, p_max)

    # Clip and cast
    data = np.clip(data, a_min=a_min, a_max=a_max)
    data -= data.min()
    data /= data.max()

    if invert:
        data = 1.0 - data

    if dtype in ("uint8", "int16"):
        data = np.round(255 * data).astype(dtype)

    return data


def _to_nifti(data, affine, filename, clip=True):
    data = np.squeeze(data)
    if clip:
        data = _advanced_clip(data)
    nii = nb.Nifti1Image(
        data,
        affine,
        None,
    )
    nii.header.set_sform(affine, code=1)
    nii.header.set_qform(affine, code=1)
    nii.to_filename(filename)
