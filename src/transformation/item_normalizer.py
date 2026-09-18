import re
import difflib
import pandas as pd
from typing import Dict, Tuple, Optional, List


class ItemNormalizer:
    """
    Intelligent 4-tier Item Normalization & Master Resolution Engine:
      1. Text Rule Normalization (whitespace, symbols, casing)
      2. Alias Dictionary Lookup (item_alias_mapping.csv)
      3. Exact Master Lookup (item_master.csv)
      4. Fuzzy Matching & Recommendation (difflib / Levenshtein confidence)
    """

    def __init__(self, master_df: pd.DataFrame, alias_df: pd.DataFrame):
        self.master_df = master_df.copy()
        self.alias_df = alias_df.copy()
        
        # Build Master Lookup Dict
        # Key: cleaned standard name -> {manufacturer, category_1, category_2, original_standard_name}
        self.master_lookup: Dict[str, Dict[str, str]] = {}
        self.standard_names_list: List[str] = []
        
        if not self.master_df.empty:
            for _, row in self.master_df.iterrows():
                std_name = str(row.get("제품명", "")).strip()
                if std_name:
                    cleaned_key = self.clean_text(std_name)
                    self.master_lookup[cleaned_key] = {
                        "standard_name": std_name,
                        "manufacturer": str(row.get("제조사", "미등록")).strip(),
                        "category_1": str(row.get("카테고리1", "기타")).strip(),
                        "category_2": str(row.get("카테고리2", "기타")).strip(),
                        "standard_volume": str(row.get("표준중량/규격", "-")).strip()
                    }
                    if std_name not in self.standard_names_list:
                        self.standard_names_list.append(std_name)

        # Build Alias Lookup Dict
        # Key: raw alias (or cleaned alias) -> standard_item_name
        self.alias_lookup: Dict[str, str] = {}
        if not self.alias_df.empty:
            for _, row in self.alias_df.iterrows():
                raw_alias = str(row.get("raw_alias", "")).strip()
                std_target = str(row.get("standard_item_name", "")).strip()
                if raw_alias and std_target:
                    self.alias_lookup[raw_alias] = std_target
                    self.alias_lookup[self.clean_text(raw_alias)] = std_target

    @staticmethod
    def clean_text(text: str) -> str:
        """Removes spaces, special characters, and converts to lowercase for lookup."""
        if not text:
            return ""
        # Remove whitespace, hyphens, underscores, slashes, brackets
        cleaned = re.sub(r'[\s\(\)\[\]\-_/·,]+', '', str(text)).lower()
        return cleaned

    def resolve_item(self, raw_item_name: str, cutoff: float = 0.65) -> Dict[str, any]:
        """
        Resolves a raw handwritten item name into standardized product metadata.
        """
        raw_clean = str(raw_item_name).strip() if raw_item_name else ""
        if not raw_clean:
            return {
                "raw_item_name": raw_item_name,
                "normalized_item_name": "미기재",
                "manufacturer": "미기재",
                "category_1": "기타",
                "category_2": "기타",
                "match_type": "EMPTY",
                "match_confidence": 0.0,
                "fuzzy_suggestion": None,
                "is_unmatched": True
            }

        cleaned_key = self.clean_text(raw_clean)

        # Tier 1: Direct Alias Match
        if raw_clean in self.alias_lookup or cleaned_key in self.alias_lookup:
            std_name = self.alias_lookup.get(raw_clean) or self.alias_lookup.get(cleaned_key)
            target_key = self.clean_text(std_name)
            info = self.master_lookup.get(target_key, {
                "standard_name": std_name,
                "manufacturer": "미등록",
                "category_1": "과자",
                "category_2": "기타",
                "standard_volume": "-"
            })
            return {
                "raw_item_name": raw_clean,
                "normalized_item_name": info["standard_name"],
                "manufacturer": info["manufacturer"],
                "category_1": info["category_1"],
                "category_2": info["category_2"],
                "standard_volume": info.get("standard_volume", "-"),
                "match_type": "ALIAS_MAPPED",
                "match_confidence": 1.0,
                "fuzzy_suggestion": None,
                "is_unmatched": False
            }

        # Tier 2: Exact Master Match (by cleaned key)
        if cleaned_key in self.master_lookup:
            info = self.master_lookup[cleaned_key]
            return {
                "raw_item_name": raw_clean,
                "normalized_item_name": info["standard_name"],
                "manufacturer": info["manufacturer"],
                "category_1": info["category_1"],
                "category_2": info["category_2"],
                "standard_volume": info.get("standard_volume", "-"),
                "match_type": "EXACT_MASTER",
                "match_confidence": 1.0,
                "fuzzy_suggestion": None,
                "is_unmatched": False
            }

        # Tier 3: Fuzzy Matching against standard names list
        fuzzy_matches = difflib.get_close_matches(raw_clean, self.standard_names_list, n=1, cutoff=cutoff)
        if fuzzy_matches:
            best_match = fuzzy_matches[0]
            score = difflib.SequenceMatcher(None, raw_clean, best_match).ratio()
            match_key = self.clean_text(best_match)
            info = self.master_lookup.get(match_key, {
                "standard_name": best_match,
                "manufacturer": "미등록",
                "category_1": "기타",
                "category_2": "기타",
                "standard_volume": "-"
            })

            # If similarity is very high (>= 0.82), we can auto-associate or flag with high confidence
            is_auto = score >= 0.82
            return {
                "raw_item_name": raw_clean,
                "normalized_item_name": info["standard_name"] if is_auto else raw_clean,
                "manufacturer": info["manufacturer"] if is_auto else "미등록",
                "category_1": info["category_1"] if is_auto else "기타",
                "category_2": info["category_2"] if is_auto else "기타",
                "standard_volume": info.get("standard_volume", "-"),
                "match_type": "FUZZY_AUTO" if is_auto else "FUZZY_SUGGESTION",
                "match_confidence": round(score, 3),
                "fuzzy_suggestion": best_match,
                "is_unmatched": not is_auto
            }

        # Tier 4: Completely Unmatched
        return {
            "raw_item_name": raw_clean,
            "normalized_item_name": raw_clean,
            "manufacturer": "미등록",
            "category_1": "기타",
            "category_2": "기타",
            "standard_volume": "-",
            "match_type": "UNMATCHED",
            "match_confidence": 0.0,
            "fuzzy_suggestion": None,
            "is_unmatched": True
        }

    def batch_normalize(self, df: pd.DataFrame, item_col: str = "item_name") -> pd.DataFrame:
        """Normalizes an entire dataframe of items."""
        results = [self.resolve_item(name) for name in df[item_col]]
        res_df = pd.DataFrame(results)
        
        # Merge back columns
        out_df = df.copy()
        out_df["normalized_item_name"] = res_df["normalized_item_name"].values
        out_df["manufacturer"] = res_df["manufacturer"].values
        out_df["category_1"] = res_df["category_1"].values
        out_df["category_2"] = res_df["category_2"].values
        out_df["standard_volume"] = res_df["standard_volume"].values
        out_df["match_type"] = res_df["match_type"].values
        out_df["match_confidence"] = res_df["match_confidence"].values
        out_df["fuzzy_suggestion"] = res_df["fuzzy_suggestion"].values
        out_df["is_unmatched_item"] = res_df["is_unmatched"].values
        return out_df
