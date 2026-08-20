import re
import subprocess
from difflib import SequenceMatcher

from .dtos import ResultItem

from .colors_analyzer import colors

phoneme_similarity = {
    # Vocales cortas y largas
    "i": {"i": 1.0, "ɪ": 0.7, "e": 0.6},
    "ɪ": {"ɪ": 1.0, "i": 0.7, "e": 0.5},
    "e": {"e": 1.0, "ɪ": 0.6, "æ": 0.5},
    "æ": {"æ": 1.0, "e": 0.5, "ɑ": 0.4},
    "ɑ": {"ɑ": 1.0, "æ": 0.4, "ʌ": 0.6},
    "ʌ": {"ʌ": 1.0, "ɑ": 0.6, "ə": 0.5},
    "ə": {"ə": 1.0, "ʌ": 0.5, "ɛ": 0.4},
    "ɔ": {"ɔ": 1.0, "ɑ": 0.7, "ʊ": 0.6},
    "ʊ": {"ʊ": 1.0, "u": 0.7, "ɔ": 0.5},
    "u": {"u": 1.0, "ʊ": 0.7, "oʊ": 0.6},
    # Diptongos
    "aɪ": {"aɪ": 1.0, "æ": 0.5, "eɪ": 0.4},
    "eɪ": {"eɪ": 1.0, "e": 0.7, "i": 0.5},
    "oʊ": {"oʊ": 1.0, "ɔ": 0.7, "u": 0.5},
    "aʊ": {"aʊ": 1.0, "æ": 0.6, "oʊ": 0.5},
    # Consonantes problematicas
    "p": {"p": 1.0, "b": 0.7, "f": 0.5, "v": 0.3},
    "b": {"b": 1.0, "p": 0.7, "v": 0.8, "f": 0.4},
    "t": {"t": 1.0, "d": 0.9, "s": 0.4, "z": 0.3, "th": 0.2},
    "d": {"d": 1.0, "t": 0.9, "z": 0.7, "s": 0.5},
    "k": {"k": 1.0, "g": 0.9, "ng": 0.6},
    "g": {"g": 1.0, "k": 0.9, "ng": 0.7},
    "s": {"s": 1.0, "z": 0.9, "sh": 0.6, "th": 0.4},
    "z": {"z": 1.0, "s": 0.9, "sh": 0.5, "d": 0.6},
    "sh": {"sh": 1.0, "s": 0.6, "zh": 0.7, "ch": 0.8},
    "zh": {"zh": 1.0, "sh": 0.7, "j": 0.8},
    "ch": {"ch": 1.0, "sh": 0.8, "t": 0.5},
    "j": {"j": 1.0, "zh": 0.8, "d": 0.6},
    "f": {"f": 1.0, "v": 0.9, "p": 0.5},
    "v": {"v": 1.0, "f": 0.9, "b": 0.7},
    "th": {"th": 1.0, "dh": 0.9, "s": 0.5, "z": 0.4},
    "dh": {"dh": 1.0, "th": 0.9, "z": 0.6},
    "ng": {"ng": 1.0, "g": 0.7, "k": 0.5},
    "n": {"n": 1.0, "m": 0.6, "ng": 0.5},
    "m": {"m": 1.0, "n": 0.6, "b": 0.5},
    "r": {"r": 1.0, "l": 0.4, "w": 0.3},
    "l": {"l": 1.0, "r": 0.4, "y": 0.5},
    "y": {"y": 1.0, "l": 0.5, "j": 0.6},
    "w": {"w": 1.0, "r": 0.3, "v": 0.5},
}


class Analyzer:
    def get_phonemes_from_speak(self, text: str):
        """Obtiene la pronunciación fonética usando eSpeak."""
        try:
            result = subprocess.run(
                ["espeak", "-q", "--ipa=3", text], capture_output=True, text=True
            )
            return result.stdout.strip().split()
        except Exception:
            return []

    def align_phonemes(self, expected, actual):
        """Alinea los fonemas esperados con los detectados usando la distancia de edición."""
        matcher = SequenceMatcher(None, expected, actual)
        aligned_expected = []
        aligned_actual = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                aligned_expected.extend(expected[i1:i2])
                aligned_actual.extend(actual[j1:j2])
            elif tag == "delete":
                aligned_expected.extend(expected[i1:i2])
                aligned_actual.extend(["-"] * (i2 - i1))  # Indica ausencia
            elif tag == "insert":
                aligned_expected.extend(["-"] * (j2 - j1))  # Indica ausencia
                aligned_actual.extend(actual[j1:j2])
            else:  # 'equal'
                aligned_expected.extend(expected[i1:i2])
                aligned_actual.extend(actual[j1:j2])

        return aligned_expected, aligned_actual

    def compare_phonemes(self, expected, actual):
        """Compara fonemas con alineación flexible y penalización progresiva."""
        expected = [re.sub(r"[ˈˌ]", "", phoneme) for phoneme in expected]
        actual = [re.sub(r"[ˈˌ]", "", phoneme) for phoneme in actual]

        aligned_expected, aligned_actual = self.align_phonemes(expected, actual)

        total_phonemes = max(len(aligned_expected), len(aligned_actual))
        similarity_score = 0.0
        result_items = []

        for exp_ph, act_ph in zip(aligned_expected, aligned_actual):
            if exp_ph == act_ph:
                similarity_score += 1.0
                # Pasamos los parámetros con keyword arguments
                result_items.append(
                    ResultItem(
                        text=f"\n{exp_ph} == {act_ph} (100%)", color=colors["good"]
                    )
                )  # "GOOD"
            elif exp_ph in phoneme_similarity and act_ph in phoneme_similarity[exp_ph]:
                score = phoneme_similarity[exp_ph][act_ph]
                similarity_score += score
                # Pasamos los parámetros con keyword arguments
                result_items.append(
                    ResultItem(
                        text=f"\n{exp_ph} ≈ {act_ph} ({score * 100:.1f}%)",
                        color=colors["warning"],
                    )
                )  # "WARNING"
            elif exp_ph == "-" or act_ph == "-":
                similarity_score += 0.0  # Penalización menor por palabras omitidas
                # Pasamos los parámetros con keyword arguments
                result_items.append(
                    ResultItem(
                        text=f"\n{exp_ph} / {act_ph} (0%)", color=colors["similar"]
                    )
                )  # "SIMILAR"
            else:
                similarity_score += 0.5  # Penalización media en lugar de 40%
                # Pasamos los parámetros con keyword arguments
                result_items.append(
                    ResultItem(
                        text=f"\n{exp_ph} != {act_ph} (50%)", color=colors["bad"]
                    )
                )  # "BAD"

        score = (similarity_score / total_phonemes) * 100 if total_phonemes > 0 else 0
        return result_items, max(0, min(100, score))
