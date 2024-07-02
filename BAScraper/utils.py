from collections import namedtuple
from dataclasses import dataclass
from typing import List


class Params:
    @dataclass
    class BAScraper:
        test: int = 0


    @dataclass
    class Arctic:
        test: int = 0


class BAUtils:
    def __init__(self):
        pass

    def _preprocess_json(self, obj):
        pass

    @staticmethod
    def _is_deleted(obj) -> bool:
        pass

    @staticmethod
    def _split_range(epoch_low: int, epoch_high: int, n: int) -> List[list]:
        segment_size = (epoch_high - epoch_low + 1) // n
        remainder = (epoch_high - epoch_low + 1) % n

        ranges = []
        current_low = epoch_low

        for i in range(n):
            current_high = current_low + segment_size - 1
            if remainder > 0:
                current_high += 1
                remainder -= 1
            ranges.append([current_low, current_high])
            current_low = current_high + 1

        return ranges
