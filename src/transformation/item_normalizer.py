import re
import difflib
import pandas as pd
from typing import Dict, Tuple, Optional, List, Any


class ItemNormalizer:
    """
    Intelligent Multi-Layer Item Normalization & Defense Buffer Engine:
      Tier 1. Direct Alias Mapping (item_alias_mapping.csv)
      Tier 2. Exact Master Lookup (cleaned key)
      Tier 3. Token-Sort Matching (Order Invariance: '콘스프 꼬북칩' == '꼬북칩 콘스프')
      Tier 4. Packaging / Specification Stripping ('신라면 120g', '초코파이 12p')
      Tier 5. Contextual Pack-Qty Disambiguation ('홈런볼' + pack_qty 12 -> 벌크, 30 -> 단품)
      Tier 6. Fuzzy Matching with Tri-Tier Confidence Gate:
              - Green (>= 0.85): Auto-mapped
              - Yellow (0.65 ~ 0.84): Suggestion for human-in-the-loop review
              - Red (< 0.65): Quarantined as unmatched
    """

    def __init__(
        self,
        master_df: pd.DataFrame,
        alias_df: pd.DataFrame,
        dim_item_df: Optional[pd.DataFrame] = None
    ):
        self.master_df = master_df.copy()
        self.alias_df = alias_df.copy()
        self.dim_item_df = dim_item_df.copy() if dim_item_df is not None else None

        # Build pack_qty lookup from dim_item or fallback loader if available
        self.pack_qty_lookup: Dict[str, int] = {}
        if self.dim_item_df is not None and not self.dim_item_df.empty:
            self._ingest_dim_item_pack_qtys(self.dim_item_df)
        else:
            try:
                from src.ingestion.loader import load_dim_item
                loaded_dim = load_dim_item()
                if loaded_dim is not None and not loaded_dim.empty:
                    self._ingest_dim_item_pack_qtys(loaded_dim)
            except Exception:
                pass

        # Build Master Lookup Dict
        # Key: cleaned standard name -> {standard_name, manufacturer, category_1, category_2, standard_volume, default_pack_qty}
        self.master_lookup: Dict[str, Dict[str, Any]] = {}
        self.token_sort_lookup: Dict[str, Dict[str, Any]] = {}
        self.standard_names_list: List[str] = []
        self.token_sort_keys_list: List[str] = []

        # Root name to variant group mapping for contextual disambiguation
        # E.g. "홈런볼" -> list of candidate variant dicts
        self.root_name_candidates: Dict[str, List[Dict[str, Any]]] = {}
        self.variant_groups: Dict[str, List[Dict[str, Any]]] = {}

        if not self.master_df.empty:
            for _, row in self.master_df.iterrows():
                std_name = str(row.get("제품명", "")).strip()
                if not std_name:
                    continue

                cleaned_key = self.clean_text(std_name)
                ts_key = self.token_sort_key(std_name)
                default_pq = self.pack_qty_lookup.get(std_name) or self.pack_qty_lookup.get(cleaned_key) or 16

                item_info = {
                    "standard_name": std_name,
                    "manufacturer": str(row.get("제조사", "미등록")).strip(),
                    "category_1": str(row.get("카테고리1", "기타")).strip(),
                    "category_2": str(row.get("카테고리2", "기타")).strip(),
                    "standard_volume": str(row.get("표준중량/규격", "-")).strip(),
                    "default_pack_qty": default_pq
                }

                self.master_lookup[cleaned_key] = item_info
                if ts_key and ts_key not in self.token_sort_lookup:
                    self.token_sort_lookup[ts_key] = item_info

                if std_name not in self.standard_names_list:
                    self.standard_names_list.append(std_name)
                if ts_key and ts_key not in self.token_sort_keys_list:
                    self.token_sort_keys_list.append(ts_key)

                # Index root keywords (e.g. "홈런볼", "에이스", "신라면", "초코파이")
                root_key = self.clean_text(self.strip_spec_noise(std_name))
                # Also split first word as base brand name
                first_word = self.clean_text(std_name.split()[0]) if " " in std_name else cleaned_key
                for rk in set([root_key, first_word]):
                    if rk and len(rk) >= 2:
                        if rk not in self.root_name_candidates:
                            self.root_name_candidates[rk] = []
                        # Avoid duplicates
                        if not any(c["standard_name"] == std_name for c in self.root_name_candidates[rk]):
                            self.root_name_candidates[rk].append(item_info)

        # Build Alias Lookup Dict
        # Key: raw alias (or cleaned/token_sorted alias) -> standard_item_name
        self.alias_lookup: Dict[str, str] = {}
        if not self.alias_df.empty:
            for _, row in self.alias_df.iterrows():
                raw_alias = str(row.get("raw_alias", "")).strip()
                std_target = str(row.get("standard_item_name", "")).strip()
                if raw_alias and std_target:
                    self.alias_lookup[raw_alias] = std_target
                    self.alias_lookup[self.clean_text(raw_alias)] = std_target

    def _ingest_dim_item_pack_qtys(self, df: pd.DataFrame):
        """Ingests default pack quantities from dim_item."""
        for _, r in df.iterrows():
            nm = str(r.get("item_name", "")).strip()
            pq = r.get("default_pack_qty")
            if nm and pd.notna(pq):
                try:
                    pq_int = int(pq)
                    self.pack_qty_lookup[nm] = pq_int
                    self.pack_qty_lookup[self.clean_text(nm)] = pq_int
                except Exception:
                    pass

    @staticmethod
    def clean_text(text: str) -> str:
        """Removes spaces, special characters, and converts to lowercase for lookup."""
        if not text:
            return ""
        cleaned = re.sub(r'[\s\(\)\[\]\-_/·,]+', '', str(text)).lower()
        return cleaned

    @staticmethod
    def token_sort_key(text: str) -> str:
        """
        Splits text by whitespace, hyphens, and punctuation, sorts tokens alphabetically,
        and joins with a space for order-independent matching.
        E.g. '콘스프 꼬북칩' -> '꼬북칩 콘스프'
        """
        if not text:
            return ""
        tokens = [t for t in re.split(r'[\s\(\)\[\]\-_/·,]+', str(text).lower()) if t]
        return " ".join(sorted(tokens))

    @staticmethod
    def strip_spec_noise(text: str) -> str:
        """
        Removes packaging/volume/specification suffixes and parenthetical notes.
        E.g. '신라면 120g' -> '신라면'
             '초코파이 12p' -> '초코파이'
             '허니버터칩(수출용)' -> '허니버터칩'
        """
        if not text:
            return ""
        s = str(text).strip()
        # Remove parenthetical / bracketed notes: (수출용), [내수], (미주용), etc.
        s = re.sub(r'\(.*?\)|\[.*?\]', '', s)
        # Remove standard weights/volumes/counts: 120g, 500ml, 12p, 5입, 10개, 4번들
        s = re.sub(r'\b\d+(\.\d+)?\s*(g|kg|ml|l|p|입|개|봉|캔|병|박스|번들|box)\b', '', s, flags=re.IGNORECASE)
        # Clean hanging separators
        s = re.sub(r'[\-_/·,]+', ' ', s)
        return s.strip()

    def _find_best_variant_by_pack_qty(self, candidates: List[Dict[str, Any]], pack_qty: int) -> Optional[Dict[str, Any]]:
        """Selects the candidate item whose default_pack_qty is closest to input pack_qty."""
        if not candidates:
            return None
        # Sort candidates by absolute distance to pack_qty
        sorted_cands = sorted(candidates, key=lambda c: abs(c.get("default_pack_qty", 16) - pack_qty))
        return sorted_cands[0]

    def _match_token_coverage(self, raw_text: str) -> Optional[str]:
        """
        Matches multi-token inputs against concatenated master items where all tokens are present
        and total character count matches (e.g. '콘스프 꼬북칩' -> '꼬북칩콘스프').
        """
        tokens = [t for t in re.split(r'[\s\(\)\[\]\-_/·,]+', str(raw_text).lower()) if t]
        if len(tokens) < 2:
            return None
        tot_len = sum(len(t) for t in tokens)
        for s in self.standard_names_list:
            c = self.clean_text(s)
            if len(c) == tot_len and all(t in c for t in tokens):
                return s
        return None

    def resolve_item(
        self,
        raw_item_name: str,
        pack_qty: Optional[int] = None,
        cutoff: float = 0.65
    ) -> Dict[str, Any]:
        """
        Resolves a raw handwritten item name into standardized product metadata
        using the 5-tier Defense Buffer Engine.
        """
        raw_clean = str(raw_item_name).strip() if raw_item_name else ""
        if not raw_clean:
            return {
                "raw_item_name": raw_item_name,
                "normalized_item_name": "미기재",
                "manufacturer": "미기재",
                "category_1": "기타",
                "category_2": "기타",
                "standard_volume": "-",
                "match_type": "EMPTY",
                "match_confidence": 0.0,
                "fuzzy_suggestion": None,
                "is_unmatched": True
            }

        cleaned_key = self.clean_text(raw_clean)
        ts_key = self.token_sort_key(raw_clean)

        # ---------------------------------------------------------
        # Tier 1: Direct Alias Match (item_alias_mapping.csv)
        # ---------------------------------------------------------
        alias_std = (
            self.alias_lookup.get(raw_clean) or
            self.alias_lookup.get(cleaned_key)
        )
        if alias_std:
            target_key = self.clean_text(alias_std)
            info = self.master_lookup.get(target_key, {
                "standard_name": alias_std,
                "manufacturer": "미등록",
                "category_1": "과자",
                "category_2": "기타",
                "standard_volume": "-",
                "default_pack_qty": 16
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

        # ---------------------------------------------------------
        # Tier 2: Exact Master Match (by cleaned key)
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # Tier 3: Token-Sort Match (Order Invariance: '콘스프 꼬북칩' == '꼬북칩 콘스프')
        # ---------------------------------------------------------
        ts_info = None
        if ts_key and ts_key in self.token_sort_lookup:
            ts_info = self.token_sort_lookup[ts_key]
        elif " " in raw_clean or "-" in raw_clean:
            cov_match = self._match_token_coverage(raw_clean)
            if cov_match:
                ts_info = self.master_lookup.get(self.clean_text(cov_match))

        if ts_info:
            return {
                "raw_item_name": raw_clean,
                "normalized_item_name": ts_info["standard_name"],
                "manufacturer": ts_info["manufacturer"],
                "category_1": ts_info["category_1"],
                "category_2": ts_info["category_2"],
                "standard_volume": ts_info.get("standard_volume", "-"),
                "match_type": "TOKEN_SORT",
                "match_confidence": 1.0,
                "fuzzy_suggestion": None,
                "is_unmatched": False
            }

        # ---------------------------------------------------------
        # Tier 4: Packaging / Specification Stripping ('신라면 120g' -> '신라면')
        # ---------------------------------------------------------
        spec_stripped = self.strip_spec_noise(raw_clean)
        if spec_stripped and spec_stripped != raw_clean:
            str_clean = self.clean_text(spec_stripped)
            str_ts = self.token_sort_key(spec_stripped)
            spec_info = None
            if str_clean in self.master_lookup:
                spec_info = self.master_lookup[str_clean]
            elif str_ts and str_ts in self.token_sort_lookup:
                spec_info = self.token_sort_lookup[str_ts]

            if spec_info:
                return {
                    "raw_item_name": raw_clean,
                    "normalized_item_name": spec_info["standard_name"],
                    "manufacturer": spec_info["manufacturer"],
                    "category_1": spec_info["category_1"],
                    "category_2": spec_info["category_2"],
                    "standard_volume": spec_info.get("standard_volume", "-"),
                    "match_type": "SPEC_STRIPPED",
                    "match_confidence": 0.95,
                    "fuzzy_suggestion": None,
                    "is_unmatched": False
                }

        # ---------------------------------------------------------
        # Tier 5: Contextual Disambiguation via pack_qty
        # (e.g. '홈런볼' + pack_qty=12 -> '홈런볼 초코 벌크', pack_qty=30 -> '홈런볼 초코')
        # ---------------------------------------------------------
        search_root = self.clean_text(spec_stripped) if spec_stripped else cleaned_key
        if search_root in self.root_name_candidates and pack_qty and pack_qty > 0:
            cands = self.root_name_candidates[search_root]
            best_variant = self._find_best_variant_by_pack_qty(cands, pack_qty)
            if best_variant:
                return {
                    "raw_item_name": raw_clean,
                    "normalized_item_name": best_variant["standard_name"],
                    "manufacturer": best_variant["manufacturer"],
                    "category_1": best_variant["category_1"],
                    "category_2": best_variant["category_2"],
                    "standard_volume": best_variant.get("standard_volume", "-"),
                    "match_type": "CONTEXT_PACK_QTY",
                    "match_confidence": 0.92,
                    "fuzzy_suggestion": None,
                    "is_unmatched": False
                }

        # ---------------------------------------------------------
        # Tier 6: Enhanced Fuzzy Matching with Tri-Tier Confidence Gate
        # ---------------------------------------------------------
        # 1. Search against standard master names
        fuzzy_matches = difflib.get_close_matches(raw_clean, self.standard_names_list, n=1, cutoff=cutoff)
        # 2. Also search spec-stripped string if available
        if not fuzzy_matches and spec_stripped and spec_stripped != raw_clean:
            fuzzy_matches = difflib.get_close_matches(spec_stripped, self.standard_names_list, n=1, cutoff=cutoff)

        if fuzzy_matches:
            best_match = fuzzy_matches[0]
            score = difflib.SequenceMatcher(None, raw_clean, best_match).ratio()
            match_key = self.clean_text(best_match)
            info = self.master_lookup.get(match_key, {
                "standard_name": best_match,
                "manufacturer": "미등록",
                "category_1": "기타",
                "category_2": "기타",
                "standard_volume": "-",
                "default_pack_qty": 16
            })

            # Tri-Tier Gating:
            # Green Zone (>= 0.85): Auto-mapped
            # Yellow Zone (0.65 ~ 0.84): Human-in-the-loop suggestion
            is_auto = score >= 0.85
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

        # Red Zone (< 0.65): Completely Unmatched / Quarantined
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

    def batch_normalize(
        self,
        df: pd.DataFrame,
        item_col: str = "item_name",
        pack_qty_col: Optional[str] = "pack_qty",
        *args,
        **kwargs
    ) -> pd.DataFrame:
        """
        Normalizes an entire dataframe of items with optional pack_qty contextual disambiguation.
        """
        has_pq = pack_qty_col and pack_qty_col in df.columns
        results = []
        for idx, row in df.iterrows():
            item_val = row[item_col]
            pq_val = None
            if has_pq:
                try:
                    raw_pq = row[pack_qty_col]
                    if pd.notna(raw_pq):
                        pq_val = int(raw_pq)
                except Exception:
                    pq_val = None
            results.append(self.resolve_item(item_val, pack_qty=pq_val))

        res_df = pd.DataFrame(results)

        # Merge back columns into new dataframe
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
