#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Specialized distribution constructors.

"""

from __future__ import division

import numpy as np
from six.moves import map, range, zip # pylint: disable=redefined-builtin

from .exceptions import ditException
from .npdist import Distribution
from .npscalardist import ScalarDistribution
from .validate import validate_pmf

__all__ = [
    'mixture_distribution',
    'mixture_distribution2',
    'modify_outcomes',
    'random_scalar_distribution',
    'random_distribution',
    'simplex_grid',
    'uniform_distribution',
    'uniform_scalar_distribution',
    'insert_rvf',
    'RVFunctions'
]

def mixture_distribution(dists, weights, merge=False):
    """
    Create a mixture distribution: $\sum p_i d_i$

    Parameters
    ----------
    dists: [Distribution]
        List of distributions to mix.  Each distribution is assumed to have
        the same base and sample space.

    weights: [float]
        List of weights to use while mixing `dists`.  The weights are assumed
        to be probability represented in the base of the distributions.

    merge: bool
        If `True` then distributions will be mixed even if they do not share
        the same sample space. The idea is that each of the input distributions
        is reinterpreted on a common, merged sample space. If `False`, then
        an exception will be raised if incompatible distributions are mixed.

    Returns
    -------
    mix: Distribution
        The mixture distribution.

    Raises
    ------
    DitException
        Raised if there `dists` and `weights` have unequal lengths.
    InvalidNormalization
        Raised if the weights do not sum to unity.
    InvalidProbability
        Raised if the weights are not valid probabilities.
    IncompatibleOutcome
        Raised if the sample spaces for each distribution are not compatible.

    """
    weights = np.asarray(weights)
    if len(dists) != len(weights):
        msg = "Length of `dists` and `weights` must be equal."
        raise ditException(msg)

    ops = dists[0].ops
    validate_pmf(weights, ops)

    if merge:
        vals = lambda o: [(ops.mult(w, d[o]) if o in d else 0)
                          for w, d in zip(weights, dists)]
    else:
        vals = lambda o: [ops.mult(w, d[o])
                          for w, d in zip(weights, dists)]

    outcomes = set().union(*[d.outcomes for d in dists])
    pmf = [ops.add_reduce(np.array(vals(o))) for o in outcomes]
    mix = dists[0].__class__(tuple(outcomes), pmf, base=ops.get_base())
    return mix

def mixture_distribution2(dists, weights):
    """
    Create a mixture distribution: $\sum p_i d_i$

    This version assumes that the pmf for each distribution is of the same
    form, and as a result, will be faster than `mixture_distribution`.
    Explicitly, it assumes that the sample space is ordered exactly the same
    for each distribution and that the outcomes currently represented in the
    pmf are the same as well. Using it in any other case will result in
    incorrect output or an exception.

    Parameters
    ----------
    dists: [Distribution]
        List of distributions to mix.  Each distribution is assumed to have
        the same base and sample space.

    weights: [float]
        List of weights to use while mixing `dists`.  The weights are assumed
        to be probability represented in the base of the distributions.

    Returns
    -------
    mix: Distribution
        The mixture distribution.

    Raises
    ------
    DitException
        Raised if there `dists` and `weights` have unequal lengths.
    InvalidNormalization
        Raised if the weights do not sum to unity.
    InvalidProbability
        Raised if the weights are not valid probabilities.
    IncompatibleDistribution
        Raised if the sample spaces for each distribution are not compatible.

    """
    weights = np.asarray(weights)
    if len(dists) != len(weights):
        msg = "Length of `dists` and `weights` must be equal."
        raise ditException(msg)

    # Also just quickly make sure that the pmfs have the same length. In
    # general, NumPy should give a value error complaining that it cannot
    # broadcast the smaller array. But if a pmf has length 1, then it can
    # be broadcast. This would make it harder to detect errors.
    shapes = set([dist.pmf.shape for dist in dists])
    if len(shapes) != 1:
        raise ValueError('All pmfs must have the same length.')

    ops = dists[0].ops
    validate_pmf(weights, ops)

    mix = dists[0].copy()
    ops.mult_inplace(mix.pmf, weights[0])
    for dist, weight in zip(dists[1:], weights[1:]):
        ops.add_inplace(mix.pmf, ops.mult(dist.pmf, weight))
    return mix

def modify_outcomes(dist, ctor):
    """
    Returns `dist` but with modified outcomes, after passing them to `ctor`.

    Parameters
    ----------
    dist : Distribution, ScalarDistribution
        The distribution to be modified.

    ctor : callable
        The constructor that receives an existing outcome and returns a new
        modified outcome.

    Returns
    -------
    d : Distribution, ScalarDistribution
        The modified distribution.

    Examples
    --------
    Convert joint tuple outcomes to strings.
    >>> d = dit.uniform_distribution(3, ['0', '1'])
    >>> d2 = dit.modify_outcomes(d, lambda x: ''.join(x))

    Increment scalar outcomes by 1.
    >>> d = dit.uniform_scalar_distribution(5)
    >>> d2 = dit.modify_outcomes(d, lambda x: x + 1)
    """
    outcomes = tuple(map(ctor, dist.outcomes))
    d = dist.__class__(outcomes, dist.pmf, base=dist.get_base())
    return d

def random_scalar_distribution(n, alpha=None, prng=None):
    """
    Returns a random scalar distribution over `n` outcomes.

    The distribution is sampled uniformly over the space of distributions on
    the `n`-simplex. If `alpha` is not `None`, then the distribution is
    sampled from the Dirichlet distribution with parameter `alpha`.

    Parameters
    ----------
    n : int | list
        The number of outcomes, or a list containing the outcomes.

    alpha : list | None
        The concentration parameters defining that the Dirichlet distribution
        used to draw the random distribution. If `None`, then each of the
        concentration parameters are set equal to 1.

    """
    import dit.math

    if prng is None:
        prng = dit.math.prng

    try:
        nOutcomes = len(n)
    except TypeError:
        nOutcomes = n

    d = uniform_scalar_distribution(nOutcomes)
    if alpha is None:
        alpha = np.ones(len(d))
    elif len(alpha) != nOutcomes:
        raise ditException('Number of concentration parameters must be `n`.')

    pmf = prng.dirichlet(alpha)
    d.pmf = pmf
    return d

def random_distribution(outcome_length, alphabet_size, alpha=None, prng=None):
    """
    Returns a random distribution drawn uniformly from the simplex.

    The distribution is sampled uniformly over the space of distributions on
    the `n`-simplex, where `n` is equal to `alphabet_size**outcome_length`.
    If `alpha` is not `None`, then the distribution is sampled from the
    Dirichlet distribution with parameter `alpha`.

    Parameters
    ----------
    outcome_length : int
        The length of the outcomes.

    alphabet_size : int, list
        The alphabet used to construct the outcomes of the distribution. If an
        integer, then the alphabet will consist of integers from 0 to k-1 where
        k is the alphabet size.  If a list, then the elements are used as the
        alphabet.

    alpha : list | None
        The concentration parameters defining that the Dirichlet distribution
        used to draw the random distribution. If `None`, then each of the
        concentration parameters are set equal to 1.

    Returns
    -------
    d : Distribution.
        A uniform sampled distribution.

    """
    import dit.math

    if prng is None:
        prng = dit.math.prng

    d = uniform_distribution(outcome_length, alphabet_size)

    if alpha is None:
        alpha = np.ones(len(d))
    elif len(alpha) != len(d):
        raise ditException('Invalid number of concentration parameters.')

    pmf = prng.dirichlet(alpha)
    d.pmf = pmf
    return d

def simplex_grid(length, depth, base=2, using=None, inplace=False):
    """Returns a generator over distributions, determined by a grid.

    The grid is "triangular" in Euclidean space.

    Parameters
    ----------
    length : int
        The number of elements in each distribution. The dimensionality
        of the simplex is length-1.
    depth : int
        Controls the density of the grid.  The number of points on the simplex
        is given by:
            (base**depth + length - 1)! / (base**depth)! / (length-1)!
        At each depth, we exponentially increase the number of points.
    base : int
        The rate at which we divide probabilities.
    using : None or distribution
        If not `None`, then each yielded distribution is a copy of `using`
        with its pmf set appropriately.  If `using` is equal to the tuple
        type, then only tuples are yielded.
    inplace : bool
        If `True`, then each yielded distribution is the same Python object,
        but with a new probability mass function. If `False`, then each yielded
        distribution is a unique Python object and can be safely stored for
        other calculations after the generator has finished. When `using` is
        equal to `tuple`, this option has no effect---all yielded tuples are
        distinct.

    Examples
    --------
    >>> list(dit.simplex_grid(2, 2, using=tuple))
    [(0.0, 1.0), (0.25, 0.75), (0.5, 0.5), (0.75, 0.25), (1.0, 0.0)]

    """
    from dit.math.combinatorics import slots

    gen = slots(int(base)**int(depth), int(length), normalized=True)

    if using == tuple:
        for pmf in gen:
            yield pmf

    else:
        if using is None:
            using = random_scalar_distribution(length)
        elif length != len(using.pmf):
            raise Exception('`length` must match the length of pmf')

        if inplace:
            d = using
            for pmf in gen:
                d.pmf[:] = pmf
                yield d
        else:
            for pmf in gen:
                d = using.copy()
                d.pmf[:] = pmf
                yield d

def uniform_scalar_distribution(n):
    """
    Returns a uniform scalar distribution over `n` outcomes.

    Parameters
    ----------
    n : int, list
        If an integer, then the outcomes are integers from 0 to n-1. If a list
        then the elements are treated as the outcomes.

    Returns
    -------
    d : ScalarDistribution
        A uniform scalar distribution.

    """
    try:
        nOutcomes = len(n)
        outcomes = n
    except TypeError:
        nOutcomes = n
        outcomes = tuple(range(n))

    pmf = [1/nOutcomes] * nOutcomes
    d = ScalarDistribution(outcomes, pmf, base='linear')

    return d

def uniform_distribution(outcome_length, alphabet_size):
    """
    Returns a uniform distribution.

    Parameters
    ----------
    outcome_length : int
        The length of the outcomes.

    alphabet_size : int, list of lists
        The alphabets used to construct the outcomes of the distribution. If an
        integer, then the alphabet for each random variable will be the same,
        consisting of integers from 0 to k-1 where k is the alphabet size.
        If a list, then the elements are used as the alphabet for each random
        variable.  If the list has a single element, then it will be used
        as the alphabet for each random variable.

    Returns
    -------
    d : Distribution.
        A uniform distribution.

    Examples
    --------
    Each random variable has the same standardized alphabet: [0,1]
    >>> d = dit.uniform_distribution(2, 2)

    Each random variable has its own alphabet.
    >>> d = dit.uniform_distribution(2, [[0,1],[1,2]])

    Both random variables have ['H','T'] as an alphabet.
    >>> d = dit.uniform_distribution(2, [['H','T']])

    """
    from itertools import product

    try:
        int(alphabet_size)
    except TypeError:
        # Assume it is a list of lists.
        alphabet = alphabet_size

        # Autoextend if only one alphabet is provided.
        if len(alphabet) == 1:
            alphabet = [alphabet[0]] * outcome_length
        elif len(alphabet) != outcome_length:
            raise TypeError("outcome_length does not match number of rvs.")
    else:
        # Build the standard alphabet.
        alphabet = [tuple(range(alphabet_size))] * outcome_length

    try:
        Z = np.prod(list(map(len, alphabet)))
    except TypeError:
        raise TypeError("alphabet_size must be an int or list of lists.")

    pmf = [1/Z] * Z
    outcomes = tuple(product(*alphabet))
    d = Distribution(outcomes, pmf, base='linear')

    return d

def insert_rvf(d, func, index=-1):
    """
    Returns a new distribution with an added random variable at index `index`.

    The new random variable must be a function of the other random variables.
    By this, we mean that the entropy of the new random variable conditioned
    on the original random variables should be zero.

    Parameters
    ----------
    dist : Distribution
        The distribution used to construct the new distribution.
    func : callable | list of callable
        A function which takes a single argument---the value of the previous
        random variables---and returns a new random variable. Note, the return
        value will be added to the outcome using `__add__`, and so it should be
        a hashable, orderable sequence (as every outcome must be). If a list of
        callables is provided, then multiple random variables are added
        simultaneously and will appear in the same order as the list.
    index : int
        The index at which to insert the random variable. A value of -1 is
        will append the random variable to the end.

    Returns
    -------
    d : Distribution
        The new distribution.

    Examples
    --------
    >>> d = dit.Distribution(['00', '01', '10', '11'], [1/4]*4)
    >>> def xor(outcome):
    ...    return str(int(outcome[0] != outcome[1]))
    ...
    >>> d2 = dit.insert_rvf(d, xor)
    >>> d.outcomes
    ('000', '011', '101', '110')

    """
    try:
        func[0]
    except TypeError:
        funcs = [func]
    else:
        funcs = func

    #print d.outcomes
    partial_outcomes = [map(func, d.outcomes) for func in funcs]
    #partial_outcomes = list(map(list,partial_outcomes))
    #print partial_outcomes
    # Now "flatten" the new contributions.
    partial_outcomes = [d._outcome_ctor([o for o_list in outcome for o in o_list])
                        for outcome in zip(*partial_outcomes)]
    #print partial_outcomes
    outcomes = [old + new for old, new in zip(d.outcomes, partial_outcomes)]
    d2 = Distribution(outcomes, d.pmf.copy(), base=d.get_base())
    return d2

class RVFunctions(object):
    """
    Helper class for building new random variables.

    Each new random variable is a function of the existing random variables.
    So for each outcome in the original distribution, there can be only one
    possible value for the new random variable.

    Some methods may make assumptions about the sample space. For example, the
    :meth:`xor` method assumes the sample space consists of 0-like and 1-like
    outcomes.

    """
    def __init__(self, d):
        """
        Initialize the random variable function creator.

        Parameters
        ----------
        d : Distribution
            The distribution used to create the new random variables.

        Examples
        --------
        >>> d = dit.Distribution(['00', '01', '10', '11'], [1/4]*4)
        >>> bf = dit.RVFunctions(d)
        >>> d = dit.insert_rvf(d, bf.xor([0,1]))
        >>> d = dit.insert_rvf(d, bf.xor([1,2]))
        >>> d.outcomes
        ('0000', '0110', '1011', '1101')

        """
        try:
            d.outcomes[0] + ''
        except TypeError:
            is_int = True
        else:
            is_int = False

        self.is_int = is_int
        self.L = d.outcome_length()
        self.ctor = d._outcome_ctor
        self.outcome_class = d._outcome_class

    def xor(self, indices):
        """
        Returns a callable which returns the logical XOR of the given indices.

        Outcomes are assumed to be strings of '0' and '1', or tuples of 0 and 1.
        The returned function handles both cases appropriately.

        Parameters
        ----------
        indices : list
            A list of two indices used to take the XOR.

        Returns
        -------
        func : function
            A callable implementing the XOR function. It receives a single
            argument, the outcome and returns an outcome for the calculation.

        Examples
        --------
        >>> d = dit.Distribution(['00', '01', '10', '11'], [1/4]*4)
        >>> bf = dit.RVFunctions(d)
        >>> d = dit.insert_rvf(d, bf.xor([0,1]))
        >>> d.outcomes
        ('000', '011', '101', '110')

        """
        if self.is_int:
            def func(outcome):
                result = outcome[indices[0]] != outcome[indices[1]]
                return (int(result),)
        else:
            def func(outcome):
                result = outcome[indices[0]] != outcome[indices[1]]
                return str(int(result))

        return func

    def from_mapping(self, mapping, force=True):
        """
        Returns a callable implementing a random variable via a mapping.

        Parameters
        ----------
        mapping : dict
            A mapping from outcomes to values of the new random variable.

        force : bool
            Ideally, the values of `mapping` should be satisfy the requirements
            of all outcomes (hashable, ordered sequences), but if `force` is
            `True`, we will attempt to use the distribution's outcome
            constructor and make sure that they are. If they are not, then
            the outcomes will be placed into a 1-tuple. This is strictly
            a convenience for users. As an example, suppose the outcomes are
            strings, the values of `mapping` can also be strings without issue.
            However, if the outcomes are tuples of integers, then the values
            *should* also be tuples. When `force` is `True`, then the values
            can be integers and then they will be transformed into 1-tuples.

        Returns
        -------
        func : function
            A callable implementing the desired function. It receives a single
            argument, the outcome, and returns an outcome for the calculation.

        Examples
        --------
        >>> d = dit.Distribution(['00', '01', '10', '11'], [1/4]*4)
        >>> bf = dit.RVFunctions(d)
        >>> mapping = {'00': '0', '01': '1', '10': '1', '11': '0'}
        >>> d = dit.insert_rvf(d, bf.from_mapping(mapping))
        >>> d.outcomes
        ('000', '011', '101', '110')

        Same example as above but now with tuples.

        >>> d = dit.Distribution([(0,0), (0,1), (1,0), (1,1)], [1/4]*4)
        >>> bf = dit.RVFunctions(d)
        >>> mapping = {(0,0): 0, (0,1): 1, (1,0): 1, (1,1): 0}
        >>> d = dit.insert_rvf(d, bf.from_mapping(mapping, force=True))
        >>> d.outcomes
        ((0, 0, 0), (0, 1, 1), (1, 0, 1), (1, 1, 0))

        See Also
        --------
        dit.modify_outcomes

        """
        ctor = self.ctor
        if force:
            try:
                list(map(ctor, mapping.values()))
            except (TypeError, ditException):
                values = [ctor([o]) for o in mapping.values()]
                mapping = dict(zip(mapping.keys(), values))

        def func(outcome):
            return mapping[outcome]

        return func

    def from_partition(self, partition):
        """
        Returns a callable implementing a function specified by a partition.

        The partition must divide the sample space of the distribution. The
        number of equivalence classes, n, determines the number of values for
        the random variable. The values are integers from 0 to n-1, but if the
        outcome class of the distribution is string, then this function will
        use the first n letters from:
            '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        as values for the random variable. So random variables with more than
        62 outcomes are not supported by this function.

        Parameters
        ----------
        partition : list
            A list of iterables. The outer list is required to determine the
            order of the new random variable

        Returns
        -------
        func : function
            A callable implementing the desired function. It receives a single
            argument, the outcome, and returns an outcome of the new random
            variable that is specified by the partition.

        Examples
        --------
        >>> d = dit.Distribution(['00', '01', '10', '11'], [1/4]*4)
        >>> bf = dit.RVFunctions(d)
        >>> partition = (('00','11'), ('01', '10'))
        >>> d = dit.insert_rvf(d, bf.from_partition(partition))
        >>> d.outcomes
        ('000', '011', '101', '110')


        """
        # Practically, we support the str class. This is bytes in Python
        # versions <3 and unicode >3.
        alphabet = '0123456789'
        letters = 'abcdefghijklmnopqrstuvwxyz'
        alphabet += letters
        alphabet += letters.upper()

        n = len(partition)
        if self.outcome_class == str:
            if n > len(alphabet):
                msg = 'Number of outcomes is too large.'
                raise NotImplementedError(msg)
            vals = alphabet[:n]
        else:
            vals = range(n)

        mapping = {}
        # Probably could do this more efficiently.
        for i, eqclass in enumerate(partition):
            for outcome in eqclass:
                mapping[self.ctor([outcome])] = vals[i]

        return self.from_mapping(mapping, force=True)

    def from_hexes(self, hexes):
        """
        Returns a callable implementing a boolean function on up to 4-bits.

        Outcomes are assumed to be strings of '0' and '1', or tuples of 0 and 1.
        The returned function handles both cases appropriately.

        The original outcomes are represented in base-16 as one of the letters
        in '0123456789ABCDEF' (not case sensitive). Then, each boolean function
        is a specification of the outcomes for which it be should true. The
        random variable will be false for the complement of this set---so this
        function additional assumes full support. For example, if the random
        variable is a function of 3-bits and should be true only for the
        outcomes 2='010' or 7='111', then `hexes` should be '27'. This nicely
        handles 1- and 2-, and 4-bit inputs in a similar fashion.

        Parameters
        ----------
        hexes : str
            A string of base-16 characters, each element represents an
            (up to) 4-bit outcome for which the random variable should be true.

        Returns
        -------
        func : function
            A callable implementing the desired function. It receives a single
            argument, the outcome, and returns an outcome for the calculation.

        Examples
        --------
        >>> outcomes = ['000', '001', '010', '011', '100', '101', '110', '111']
        >>> pmf = [1/8] * 8
        >>> d = dit.Distribution(outcomes, pmf)
        >>> bf = dit.RVFunctions(d)
        >>> d = dit.insert_rvf(d, bf.from_hexes('27'))
        >>> d.outcomes
        ('0000', '0010', '0101', '0110', '1000', '1010', '1100', '1111')

        """
        base = 16
        template = "{0:0{1}b}"
        outcomes = [template.format(int(h, base), self.L) for h in hexes]
        if self.is_int:
            outcomes = [tuple(map(int, o)) for o in outcomes]
        outcomes = set(outcomes)

        if self.is_int:
            def func(outcome):
                result = outcome in outcomes
                return (int(result),)
        else:
            def func(outcome):
                result = outcome in outcomes
                return str(int(result))
        return func
