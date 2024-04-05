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
"""Utils to sort the DWI data volume indices"""

import numpy as np


def linear_action(size, **kwargs):
    """
    Sort the DWI data volume indices linearly

    Parameters
    ----------
    size : :obj:`int`
        Number of volumes in the dataset
        (for instance, the number of orientations in a DWI)

    Returns
    -------
    :obj:`list` of :obj:`int`
        The sorted index order.

    Examples
    --------
    >>> list(linear_action(10))
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    """
    return range(size)


def random_action(size, **kwargs):
    """Sort the DWI data volume indices.

    Parameters
    ----------
    size : :obj:`int`
        Number of volumes in the dataset
        (for instance, the number of orientations in a DWI)

    Returns
    -------
    index_order : :obj:`numpy.ndarray`
        The sorted index order.
    """

    _seed = kwargs.get('seed', None)
    if kwargs.get('seed', None) or kwargs.get('seed', None) == 0:
        _seed = 20210324 if kwargs.get('seed', None) is True else kwargs.get('seed', None)

    rng = np.random.default_rng(_seed)

    index_order = np.arange(size)
    rng.shuffle(index_order)

    return index_order.to_list()


def bvalue_action(gradients):
    """
    Sort the DWI data volume indices in ascending order based on the last column of gradients.

    Parameters
    ----------
    gradients : :obj:`numpy.ndarray` gradient table of the dataset

    Examples
    --------
    >>> bvalue_action(np.array([[1, 1, 1, 1], [4, 4, 4, 4], [2, 2, 2, 2]]))
    array([0, 2, 1])

    Returns
    -------
    numpy.ndarray: The sorted index order.
    """
    last_column = gradients[:, -1]
    index_order = np.argsort(last_column)
    return index_order


def centralsym_action(size, **kwargs):
    """
    Sort the DWI data volume indices in a central symmetric manner.

    Parameters
    ----------
    size : :obj:`int`
        Number of volumes in the dataset
        (for instance, the number of orientations in a DWI)

    Examples
    --------
    >>> centralsym_action(10)
    [5, 4, 6, 3, 7, 2, 8, 1, 9, 0]
    >>> centralsym_action(11)
    [5, 4, 6, 3, 7, 2, 8, 1, 9, 0, 10]

    Returns
    -------
    :obj:`list` of :obj:`int`
        The sorted index order.
    """
    linear = list(range(size))
    half1, half2 = list(reversed(linear[:size // 2])), linear[size // 2:]
    index_order = [
        sub[item] for item in range(len(half1))
        for sub in [half2, half1]
    ]
    if size % 2:  # If size is odd number, append last element
        index_order.append(half2[-1])
    return index_order