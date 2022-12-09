def check_digit_10(isbn):
    assert len(isbn) == 9
    sum = 0
    for i in range(len(isbn)):
        c = int(isbn[i])
        w = i + 1
        sum += w * c
    r = sum % 11
    return 'X' if r == 10 else str(r)


def check_digit_13(isbn):
    assert len(isbn) == 12
    sum = 0
    for i in range(len(isbn)):
        c = int(isbn[i])
        w = 3 if i % 2 else 1
        sum += w * c
    r = 10 - (sum % 10)
    return '0' if r == 10 else str(r)


def isbn_10_to_13(isbn):
    if not isbn or len(isbn) != 10:
        return None
    return '978' + isbn[:-1] + check_digit_13('978' + isbn[:-1])


def isbn_13_to_10(isbn):
    if not isbn or len(isbn) != 13 or isbn[:3] != '978':
        return None
    else:
        return isbn[3:12] + check_digit_10(isbn[3:12])


def is_isbn_13(isbn):
    return len(isbn) == 13


def is_isbn_10(isbn):
    return len(isbn) == 10 and isbn[0] >= '0' and isbn[0] <= '9'


def is_asin(asin):
    return len(asin) == 10 and asin[0].lower == 'b'
