# Путь: utils/helpers.py
import random

class Helpers:
    @staticmethod
    def roll(args):
        # /roll -> 1-100, /roll 50 100 -> 50-100
        try:
            if len(args) >= 2:
                m_min, m_max = int(args[0]), int(args[1])
            else:
                m_min, m_max = 1, 100
            return str(random.randint(m_min, m_max))
        except:
            return str(random.randint(1, 100))

    @staticmethod
    def yn():
        return random.choice(["yes", "no"])