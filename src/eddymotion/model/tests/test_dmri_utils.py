# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2024 The NiPreps Developers <nipreps@gmail.com>
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
from pathlib import Path

import numpy as np
import pytest

from eddymotion.model.dmri_utils import (
    find_shelling_scheme,
)

_datadir = (Path(__file__).parent.parent.parent / "data").absolute()


@pytest.mark.parametrize(
    ("bvals", "exp_scheme", "exp_bval_groups", "exp_bval_estimated"),
    [
        (
            np.asarray(
                [
                    5,
                    300,
                    300,
                    300,
                    300,
                    300,
                    305,
                    1005,
                    995,
                    1000,
                    1000,
                    1005,
                    1000,
                    1000,
                    1005,
                    995,
                    1000,
                    1005,
                    5,
                    995,
                    1000,
                    1000,
                    995,
                    1005,
                    995,
                    1000,
                    995,
                    995,
                    2005,
                    2000,
                    2005,
                    2005,
                    1995,
                    2000,
                    2005,
                    2000,
                    1995,
                    2005,
                    5,
                    1995,
                    2005,
                    1995,
                    1995,
                    2005,
                    2005,
                    1995,
                    2000,
                    2000,
                    2000,
                    1995,
                    2000,
                    2000,
                    2005,
                    2005,
                    1995,
                    2005,
                    2005,
                    1990,
                    1995,
                    1995,
                    1995,
                    2005,
                    2000,
                    1990,
                    2010,
                    5,
                ]
            ),
            "multi-shell",
            [
                np.asarray([5, 5, 5, 5]),
                np.asarray([300, 300, 300, 300, 300, 305]),
                np.asarray(
                    [
                        1005,
                        995,
                        1000,
                        1000,
                        1005,
                        1000,
                        1000,
                        1005,
                        995,
                        1000,
                        1005,
                        995,
                        1000,
                        1000,
                        995,
                        1005,
                        995,
                        1000,
                        995,
                        995,
                    ]
                ),
                np.asarray(
                    [
                        2005,
                        2000,
                        2005,
                        2005,
                        1995,
                        2000,
                        2005,
                        2000,
                        1995,
                        2005,
                        1995,
                        2005,
                        1995,
                        1995,
                        2005,
                        2005,
                        1995,
                        2000,
                        2000,
                        2000,
                        1995,
                        2000,
                        2000,
                        2005,
                        2005,
                        1995,
                        2005,
                        2005,
                        1990,
                        1995,
                        1995,
                        1995,
                        2005,
                        2000,
                        1990,
                        2010,
                    ]
                ),
            ],
            [5, 300, 1000, 2000],
        ),
    ],
)
def test_find_shelling_scheme_array(bvals, exp_scheme, exp_bval_groups, exp_bval_estimated):
    obt_scheme, obt_bval_groups, obt_bval_estimated = find_shelling_scheme(bvals)
    assert obt_scheme == exp_scheme
    assert all(
        np.allclose(obt_arr, exp_arr)
        for obt_arr, exp_arr in zip(obt_bval_groups, exp_bval_groups, strict=True)
    )
    assert np.allclose(obt_bval_estimated, exp_bval_estimated)


@pytest.mark.parametrize(
    ("dwi_btable", "exp_scheme", "exp_bval_groups", "exp_bval_estimated"),
    [
        (
            "ds000114_singleshell",
            "single-shell",
            [
                np.asarray([0, 0, 0, 0, 0, 0, 0]),
                np.asarray(
                    [
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                    ]
                ),
            ],
            [0.0, 1000.0],
        ),
        (
            "hcph_multishell",
            "multi-shell",
            [
                np.asarray([0, 0, 0, 0, 0, 0]),
                np.asarray([700, 700, 700, 700, 700, 700, 700, 700, 700, 700, 700, 700]),
                np.asarray(
                    [
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                        1000,
                    ]
                ),
                np.asarray(
                    [
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                        2000,
                    ]
                ),
                np.asarray(
                    [
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                        3000,
                    ]
                ),
            ],
            [0.0, 700.0, 1000.0, 2000.0, 3000.0],
        ),
        (
            "ds004737_dsi",
            "DSI",
            [
                np.asarray([5, 5, 5, 5, 5, 5, 5, 5, 5]),
                np.asarray([995, 995, 800, 800, 995, 995, 795, 995]),
                np.asarray([1195, 1195, 1195, 1195, 1000, 1195, 1195, 1000]),
                np.asarray([1595, 1595, 1595, 1600.0]),
                np.asarray(
                    [
                        1800,
                        1795,
                        1795,
                        1790,
                        1995,
                        1800,
                        1795,
                        1990,
                        1990,
                        1795,
                        1990,
                        1795,
                        1795,
                        1995,
                    ]
                ),
                np.asarray([2190, 2195, 2190, 2195, 2000, 2000, 2000, 2195, 2195, 2190]),
                np.asarray([2590, 2595, 2600, 2395, 2595, 2600, 2395]),
                np.array([2795, 2790, 2795, 2795, 2790, 2795, 2795, 2790, 2795]),
                np.array([3590, 3395, 3595, 3595, 3395, 3395, 3400]),
                np.array([3790, 3790]),
                np.array([4195, 4195]),
                np.array([4390, 4395, 4390]),
                np.array(
                    [
                        4790,
                        4990,
                        4990,
                        5000,
                        5000,
                        4990,
                        4795,
                        4985,
                        5000,
                        4795,
                        5000,
                        4990,
                        4990,
                        4790,
                        5000,
                        4990,
                        4795,
                        4795,
                        4990,
                        5000,
                        4990,
                    ]
                ),
            ],
            [
                5.0,
                995.0,
                1195.0,
                1595.0,
                1797.5,
                2190.0,
                2595.0,
                2795.0,
                3400.0,
                3790.0,
                4195.0,
                4390.0,
                4990.0,
            ],
        ),
    ],
)
def test_find_shelling_scheme_files(dwi_btable, exp_scheme, exp_bval_groups, exp_bval_estimated):
    bvals = np.loadtxt(_datadir / f"{dwi_btable}.bval")

    obt_scheme, obt_bval_groups, obt_bval_estimated = find_shelling_scheme(bvals)
    assert obt_scheme == exp_scheme
    assert all(
        np.allclose(obt_arr, exp_arr)
        for obt_arr, exp_arr in zip(obt_bval_groups, exp_bval_groups, strict=True)
    )
    assert np.allclose(obt_bval_estimated, exp_bval_estimated)
