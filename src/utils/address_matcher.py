import re
from typing import Set

class AddressMatcher:
    """Smart engine for parsing Bosnian house number formats and matching them."""

    @staticmethod
    def normalize(house_number: str) -> str:
        """Cleans a house number for comparison (e.g., ' 4 a ' -> '4A')."""
        if not house_number:
            return ""
        # Remove all whitespace and convert to uppercase
        num = re.sub(r"\s+", "", house_number).upper()
        # Normalize BB variations
        if num in ["BB", "B.B.", "BB.", "B.B"]:
            return "BB"
        return num

    @classmethod
    def expand_outage_numbers(cls, raw_numbers: str) -> Set[str]:
        """
        Takes a raw EPBiH house number string and expands it into a set of precise matches.
        """
        if not raw_numbers:
            return set()

        expanded = set()
        parts = [p.strip() for p in raw_numbers.split(",")]
        
        for part in parts:
            if not part:
                continue
                
            clean_part = cls.normalize(part)
            
            # Rule 1: Pure Range (e.g., "13-15")
            range_match = re.match(r"^(\d+)-(\d+)$", clean_part)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                if start > end:
                    start, end = end, start  # Swap if backwards
                for i in range(start, end + 1):
                    expanded.add(str(i))
                continue
                
            # Rule 2: DO X (Up to X)
            do_match = re.match(r"^DO(\d+)$", clean_part)
            if do_match:
                end_num = int(do_match.group(1))
                for i in range(1, end_num + 1):
                    expanded.add(str(i))
                continue
                
            # Rule 3: OD X DO Y (From X to Y)
            od_do_match = re.match(r"^OD(\d+)DO(\d+)$", clean_part)
            if od_do_match:
                start, end = int(od_do_match.group(1)), int(od_do_match.group(2))
                if start > end:
                    start, end = end, start
                for i in range(start, end + 1):
                    expanded.add(str(i))
                continue

            # Default: add the cleaned alphanumeric string
            expanded.add(clean_part)
            
        return expanded

    @classmethod
    def is_match(cls, user_house_number: str, raw_outage_numbers: str) -> bool:
        """
        Master function: Does the user's house fall inside the outage area?
        """
        # Rule A: Provider Wildcard. If EPBiH gives no numbers, the whole street/village is down.
        if not raw_outage_numbers or raw_outage_numbers.strip() == "":
            return True 
            
        # Rule B: User Wildcard. If the user gives no number (rural), they get alerts for the whole street/village.
        if not user_house_number or user_house_number.strip() == "":
            return True
            
        normalized_user = cls.normalize(user_house_number)
        expanded_outage = cls.expand_outage_numbers(raw_outage_numbers)
        
        return normalized_user in expanded_outage
