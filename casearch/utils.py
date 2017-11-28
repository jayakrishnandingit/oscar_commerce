def get_price_range_tuple(start=500, step=500, end=50000):
    return list(zip(xrange(start, (end + step), step), xrange(start, (end + step), step)))
