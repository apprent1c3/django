# Copyright (c) 2008-2009 Aryeh Leib Taurog, http://www.aryehleib.com
# All rights reserved.
#
# Modified from original contribution by Aryeh Leib Taurog, which was
# released under the New BSD license.

import unittest

from django.contrib.gis.geos.mutable_list import ListMixin


class UserListA(ListMixin):
    _mytype = tuple

    def __init__(self, i_list, *args, **kwargs):
        self._list = self._mytype(i_list)
        super().__init__(*args, **kwargs)

    def __len__(self):
        return len(self._list)

    def __str__(self):
        return str(self._list)

    def __repr__(self):
        return repr(self._list)

    def _set_list(self, length, items):
        # this would work:
        # self._list = self._mytype(items)
        # but then we wouldn't be testing length parameter
        itemList = ["x"] * length
        for i, v in enumerate(items):
            itemList[i] = v

        self._list = self._mytype(itemList)

    def _get_single_external(self, index):
        return self._list[index]


class UserListB(UserListA):
    _mytype = list

    def _set_single(self, index, value):
        self._list[index] = value


def nextRange(length):
    nextRange.start += 100
    return range(nextRange.start, nextRange.start + length)


nextRange.start = 0


class ListMixinTest(unittest.TestCase):
    """
    Tests base class ListMixin by comparing a list clone which is
    a ListMixin subclass with a real Python list.
    """

    limit = 3
    listType = UserListA

    def lists_of_len(self, length=None):
        if length is None:
            length = self.limit
        pl = list(range(length))
        return pl, self.listType(pl)

    def limits_plus(self, b):
        return range(-self.limit - b, self.limit + b)

    def step_range(self):
        return [*range(-1 - self.limit, 0), *range(1, 1 + self.limit)]

    def test01_getslice(self):
        """
        Tests the slice retrieval functionality of lists, ensuring that slices of different types (start, stop, step) are correctly retrieved and compared.
        """
        pl, ul = self.lists_of_len()
        for i in self.limits_plus(1):
            self.assertEqual(pl[i:], ul[i:], "slice [%d:]" % (i))
            self.assertEqual(pl[:i], ul[:i], "slice [:%d]" % (i))

            for j in self.limits_plus(1):
                self.assertEqual(pl[i:j], ul[i:j], "slice [%d:%d]" % (i, j))
                for k in self.step_range():
                    self.assertEqual(
                        pl[i:j:k], ul[i:j:k], "slice [%d:%d:%d]" % (i, j, k)
                    )

            for k in self.step_range():
                self.assertEqual(pl[i::k], ul[i::k], "slice [%d::%d]" % (i, k))
                self.assertEqual(pl[:i:k], ul[:i:k], "slice [:%d:%d]" % (i, k))

        for k in self.step_range():
            self.assertEqual(pl[::k], ul[::k], "slice [::%d]" % (k))

    def test02_setslice(self):
        """
        Tests various slice assignment scenarios for a list, including 
        starting and ending indices, step sizes, and edge cases, to ensure 
        they behave as expected when modified through Python's slice syntax.
        """

        def setfcn(x, i, j, k, L):
            x[i:j:k] = range(L)

        pl, ul = self.lists_of_len()
        for slen in range(self.limit + 1):
            ssl = nextRange(slen)
            ul[:] = ssl
            pl[:] = ssl
            self.assertEqual(pl, ul[:], "set slice [:]")

            for i in self.limits_plus(1):
                ssl = nextRange(slen)
                ul[i:] = ssl
                pl[i:] = ssl
                self.assertEqual(pl, ul[:], "set slice [%d:]" % (i))

                ssl = nextRange(slen)
                ul[:i] = ssl
                pl[:i] = ssl
                self.assertEqual(pl, ul[:], "set slice [:%d]" % (i))

                for j in self.limits_plus(1):
                    ssl = nextRange(slen)
                    ul[i:j] = ssl
                    pl[i:j] = ssl
                    self.assertEqual(pl, ul[:], "set slice [%d:%d]" % (i, j))

                    for k in self.step_range():
                        ssl = nextRange(len(ul[i:j:k]))
                        ul[i:j:k] = ssl
                        pl[i:j:k] = ssl
                        self.assertEqual(pl, ul[:], "set slice [%d:%d:%d]" % (i, j, k))

                        sliceLen = len(ul[i:j:k])
                        with self.assertRaises(ValueError):
                            setfcn(ul, i, j, k, sliceLen + 1)
                        if sliceLen > 2:
                            with self.assertRaises(ValueError):
                                setfcn(ul, i, j, k, sliceLen - 1)

                for k in self.step_range():
                    ssl = nextRange(len(ul[i::k]))
                    ul[i::k] = ssl
                    pl[i::k] = ssl
                    self.assertEqual(pl, ul[:], "set slice [%d::%d]" % (i, k))

                    ssl = nextRange(len(ul[:i:k]))
                    ul[:i:k] = ssl
                    pl[:i:k] = ssl
                    self.assertEqual(pl, ul[:], "set slice [:%d:%d]" % (i, k))

            for k in self.step_range():
                ssl = nextRange(len(ul[::k]))
                ul[::k] = ssl
                pl[::k] = ssl
                self.assertEqual(pl, ul[:], "set slice [::%d]" % (k))

    def test03_delslice(self):
        """
        Tests the deletion of slices from lists using various slice notation combinations, 
        including start, stop, and step parameters, to ensure the behavior is as expected.
        """
        for Len in range(self.limit):
            pl, ul = self.lists_of_len(Len)
            del pl[:]
            del ul[:]
            self.assertEqual(pl[:], ul[:], "del slice [:]")
            for i in range(-Len - 1, Len + 1):
                pl, ul = self.lists_of_len(Len)
                del pl[i:]
                del ul[i:]
                self.assertEqual(pl[:], ul[:], "del slice [%d:]" % (i))
                pl, ul = self.lists_of_len(Len)
                del pl[:i]
                del ul[:i]
                self.assertEqual(pl[:], ul[:], "del slice [:%d]" % (i))
                for j in range(-Len - 1, Len + 1):
                    pl, ul = self.lists_of_len(Len)
                    del pl[i:j]
                    del ul[i:j]
                    self.assertEqual(pl[:], ul[:], "del slice [%d:%d]" % (i, j))
                    for k in [*range(-Len - 1, 0), *range(1, Len)]:
                        pl, ul = self.lists_of_len(Len)
                        del pl[i:j:k]
                        del ul[i:j:k]
                        self.assertEqual(
                            pl[:], ul[:], "del slice [%d:%d:%d]" % (i, j, k)
                        )

                for k in [*range(-Len - 1, 0), *range(1, Len)]:
                    pl, ul = self.lists_of_len(Len)
                    del pl[:i:k]
                    del ul[:i:k]
                    self.assertEqual(pl[:], ul[:], "del slice [:%d:%d]" % (i, k))

                    pl, ul = self.lists_of_len(Len)
                    del pl[i::k]
                    del ul[i::k]
                    self.assertEqual(pl[:], ul[:], "del slice [%d::%d]" % (i, k))

            for k in [*range(-Len - 1, 0), *range(1, Len)]:
                pl, ul = self.lists_of_len(Len)
                del pl[::k]
                del ul[::k]
                self.assertEqual(pl[:], ul[:], "del slice [::%d]" % (k))

    def test04_get_set_del_single(self):
        """
        Test the functionality of getting, setting, and deleting single items in a list, ensuring that the list behaves as expected under various index values.
        """
        pl, ul = self.lists_of_len()
        for i in self.limits_plus(0):
            self.assertEqual(pl[i], ul[i], "get single item [%d]" % i)

        for i in self.limits_plus(0):
            pl, ul = self.lists_of_len()
            pl[i] = 100
            ul[i] = 100
            self.assertEqual(pl[:], ul[:], "set single item [%d]" % i)

        for i in self.limits_plus(0):
            pl, ul = self.lists_of_len()
            del pl[i]
            del ul[i]
            self.assertEqual(pl[:], ul[:], "del single item [%d]" % i)

    def test05_out_of_range_exceptions(self):
        """
        Tests that out of range index errors are correctly raised when attempting to set, get, or delete items from a list at invalid indices.
        """

        def setfcn(x, i):
            x[i] = 20

        def getfcn(x, i):
            return x[i]

        def delfcn(x, i):
            del x[i]

        pl, ul = self.lists_of_len()
        for i in (-1 - self.limit, self.limit):
            with self.assertRaises(IndexError):  # 'set index %d' % i)
                setfcn(ul, i)
            with self.assertRaises(IndexError):  # 'get index %d' % i)
                getfcn(ul, i)
            with self.assertRaises(IndexError):  # 'del index %d' % i)
                delfcn(ul, i)

    def test06_list_methods(self):
        """
        Compares the functionality of list methods between two lists.

        Tests the equivalence of various list operations, including append, extend, 
        reverse, insert, pop, index, count, and remove, between two lists. 
        Ensures that the lists remain equal after each operation and that they 
        raise the expected exceptions when called with invalid indices or values.
        """
        pl, ul = self.lists_of_len()
        pl.append(40)
        ul.append(40)
        self.assertEqual(pl[:], ul[:], "append")

        pl.extend(range(50, 55))
        ul.extend(range(50, 55))
        self.assertEqual(pl[:], ul[:], "extend")

        pl.reverse()
        ul.reverse()
        self.assertEqual(pl[:], ul[:], "reverse")

        for i in self.limits_plus(1):
            pl, ul = self.lists_of_len()
            pl.insert(i, 50)
            ul.insert(i, 50)
            self.assertEqual(pl[:], ul[:], "insert at %d" % i)

        for i in self.limits_plus(0):
            pl, ul = self.lists_of_len()
            self.assertEqual(pl.pop(i), ul.pop(i), "popped value at %d" % i)
            self.assertEqual(pl[:], ul[:], "after pop at %d" % i)

        pl, ul = self.lists_of_len()
        self.assertEqual(pl.pop(), ul.pop(i), "popped value")
        self.assertEqual(pl[:], ul[:], "after pop")

        pl, ul = self.lists_of_len()

        def popfcn(x, i):
            x.pop(i)

        with self.assertRaises(IndexError):
            popfcn(ul, self.limit)
        with self.assertRaises(IndexError):
            popfcn(ul, -1 - self.limit)

        pl, ul = self.lists_of_len()
        for val in range(self.limit):
            self.assertEqual(pl.index(val), ul.index(val), "index of %d" % val)

        for val in self.limits_plus(2):
            self.assertEqual(pl.count(val), ul.count(val), "count %d" % val)

        for val in range(self.limit):
            pl, ul = self.lists_of_len()
            pl.remove(val)
            ul.remove(val)
            self.assertEqual(pl[:], ul[:], "after remove val %d" % val)

        def indexfcn(x, v):
            return x.index(v)

        def removefcn(x, v):
            return x.remove(v)

        with self.assertRaises(ValueError):
            indexfcn(ul, 40)
        with self.assertRaises(ValueError):
            removefcn(ul, 40)

    def test07_allowed_types(self):
        """
        Verifies that a list enforces type restrictions when assigning values.
        """
        pl, ul = self.lists_of_len()
        ul._allowed = int
        ul[1] = 50
        ul[:2] = [60, 70, 80]

        def setfcn(x, i, v):
            x[i] = v

        with self.assertRaises(TypeError):
            setfcn(ul, 2, "hello")
        with self.assertRaises(TypeError):
            setfcn(ul, slice(0, 3, 2), ("hello", "goodbye"))

    def test08_min_length(self):
        """
        Tests the minimum length constraint of a list.

        Verifies that attempting to delete or set elements below the minimum length threshold raises a ValueError, 
        and that appending elements beyond the minimum length up to the maximum length is allowed, 
        but attempting to append beyond the maximum length threshold raises a ValueError.
        """
        pl, ul = self.lists_of_len(5)
        ul._minlength = 3

        def delfcn(x, i):
            del x[:i]

        def setfcn(x, i):
            x[:i] = []

        for i in range(len(ul) - ul._minlength + 1, len(ul)):
            with self.assertRaises(ValueError):
                delfcn(ul, i)
            with self.assertRaises(ValueError):
                setfcn(ul, i)
        del ul[: len(ul) - ul._minlength]

        ul._maxlength = 4
        for i in range(0, ul._maxlength - len(ul)):
            ul.append(i)
        with self.assertRaises(ValueError):
            ul.append(10)

    def test09_iterable_check(self):
        """
        Verifies that attempting to assign a non-iterable value to a slice raises a TypeError, ensuring that slices can only be assigned iterable values.
        """
        pl, ul = self.lists_of_len(self.limit + 1)

        def setfcn(x, i, v):
            x[i] = v

        with self.assertRaises(TypeError):
            setfcn(ul, slice(0, 3, 2), 2)

    def test10_checkindex(self):
        """
        Tests that the _checkindex method correctly handles index values within and outside the valid range, ensuring negative indices are adjusted and out-of-bounds indices raise an IndexError.
        """
        pl, ul = self.lists_of_len()
        for i in self.limits_plus(0):
            if i < 0:
                self.assertEqual(
                    ul._checkindex(i), i + self.limit, "_checkindex(neg index)"
                )
            else:
                self.assertEqual(ul._checkindex(i), i, "_checkindex(pos index)")

        for i in (-self.limit - 1, self.limit):
            with self.assertRaises(IndexError):
                ul._checkindex(i)

    def test_11_sorting(self):
        """
        Tests the sorting functionality of lists, covering default sort, sort with a custom key function, and reverse sorting to ensure consistency across different sorting scenarios.
        """
        pl, ul = self.lists_of_len()
        pl.insert(0, pl.pop())
        ul.insert(0, ul.pop())
        pl.sort()
        ul.sort()
        self.assertEqual(pl[:], ul[:], "sort")
        mid = pl[len(pl) // 2]
        pl.sort(key=lambda x: (mid - x) ** 2)
        ul.sort(key=lambda x: (mid - x) ** 2)
        self.assertEqual(pl[:], ul[:], "sort w/ key")

        pl.insert(0, pl.pop())
        ul.insert(0, ul.pop())
        pl.sort(reverse=True)
        ul.sort(reverse=True)
        self.assertEqual(pl[:], ul[:], "sort w/ reverse")
        mid = pl[len(pl) // 2]
        pl.sort(key=lambda x: (mid - x) ** 2)
        ul.sort(key=lambda x: (mid - x) ** 2)
        self.assertEqual(pl[:], ul[:], "sort w/ key")

    def test_12_arithmetic(self):
        """
        Tests the arithmetic and comparison operations of two list-like objects, including addition, multiplication, and inequality checks, to ensure they behave as expected.
        """
        pl, ul = self.lists_of_len()
        al = list(range(10, 14))
        self.assertEqual(list(pl + al), list(ul + al), "add")
        self.assertEqual(type(ul), type(ul + al), "type of add result")
        self.assertEqual(list(al + pl), list(al + ul), "radd")
        self.assertEqual(type(al), type(al + ul), "type of radd result")
        objid = id(ul)
        pl += al
        ul += al
        self.assertEqual(pl[:], ul[:], "in-place add")
        self.assertEqual(objid, id(ul), "in-place add id")

        for n in (-1, 0, 1, 3):
            pl, ul = self.lists_of_len()
            self.assertEqual(list(pl * n), list(ul * n), "mul by %d" % n)
            self.assertEqual(type(ul), type(ul * n), "type of mul by %d result" % n)
            self.assertEqual(list(n * pl), list(n * ul), "rmul by %d" % n)
            self.assertEqual(type(ul), type(n * ul), "type of rmul by %d result" % n)
            objid = id(ul)
            pl *= n
            ul *= n
            self.assertEqual(pl[:], ul[:], "in-place mul by %d" % n)
            self.assertEqual(objid, id(ul), "in-place mul by %d id" % n)

        pl, ul = self.lists_of_len()
        self.assertEqual(pl, ul, "cmp for equal")
        self.assertNotEqual(ul, pl + [2], "cmp for not equal")
        self.assertGreaterEqual(pl, ul, "cmp for gte self")
        self.assertLessEqual(pl, ul, "cmp for lte self")
        self.assertGreaterEqual(ul, pl, "cmp for self gte")
        self.assertLessEqual(ul, pl, "cmp for self lte")

        self.assertGreater(pl + [5], ul, "cmp")
        self.assertGreaterEqual(pl + [5], ul, "cmp")
        self.assertLess(pl, ul + [2], "cmp")
        self.assertLessEqual(pl, ul + [2], "cmp")
        self.assertGreater(ul + [5], pl, "cmp")
        self.assertGreaterEqual(ul + [5], pl, "cmp")
        self.assertLess(ul, pl + [2], "cmp")
        self.assertLessEqual(ul, pl + [2], "cmp")

        pl[1] = 20
        self.assertGreater(pl, ul, "cmp for gt self")
        self.assertLess(ul, pl, "cmp for self lt")
        pl[1] = -20
        self.assertLess(pl, ul, "cmp for lt self")
        self.assertGreater(ul, pl, "cmp for gt self")


class ListMixinTestSingle(ListMixinTest):
    listType = UserListB
