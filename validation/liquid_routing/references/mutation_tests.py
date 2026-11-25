"""Show that `self_check.py` can fail: each deliberate change of a published file must be flagged.

    python -B -P mutation_tests.py --out DIR --scratch SCRATCH --inputs SPEC/inputs.json

Works on copies of `reference_invented.json` (every kind of world, plant and event in one file), in SCRATCH only. Writes
`mutation_tests.json` into DIR and exits with 1 if the unchanged file is flagged or a change is not.
"""

import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MUTATIONS = []


def mutation(name):
    def register(function):
        MUTATIONS.append((name, function))
        return function
    return register


def bump(text, digit):
    """The published string with one significant digit (1-based) moved by one."""
    sign, body = ("-", text[1:]) if text[0] == "-" else ("", text)
    mantissa, exponent = body.split("E")
    digits = list(mantissa.replace(".", ""))
    digits[digit - 1] = str((int(digits[digit - 1]) + 1) % 10)
    return f"{sign}{digits[0]}.{''.join(digits[1:])}E{exponent}"


def series(document, world, name):
    return document["worlds"][world]["series"][name]


def plant(document, name):
    return [row for row in document["plants"] if row["plant"] == name][0]


@mutation("an amount changed in its 38th digit")
def _(d):
    v = series(d, "inv-F1", "n_T_K")["value"]
    v[5] = bump(v[5], 38)


@mutation("an amount of the loop changed in its 30th digit")
def _(d):
    v = series(d, "inv-F6", "n_U_C")["value"]
    v[5] = bump(v[5], 30)


@mutation("a class E at t = 0 made R")
def _(d):
    series(d, "inv-F1", "H_tot")["class"][0] = "R"


@mutation("a series missing")
def _(d):
    del d["worlds"]["inv-F2"]["series"]["supplied_U"]


@mutation("the two directions' collectors swapped")
def _(d):
    a, b = d["worlds"]["inv-F1"]["series"], d["worlds"]["inv-F2"]["series"]
    a["n_T_K"], b["n_T_K"] = b["n_T_K"], a["n_T_K"]


@mutation("a holder's heat changed in its 22nd digit")
def _(d):
    v = series(d, "inv-H1", "H_B")["value"]
    v[3] = bump(v[3], 22)


@mutation("two holders' heats swapped")
def _(d):
    s = d["worlds"]["inv-H1"]["series"]
    s["H_A"], s["H_B"] = s["H_B"], s["H_A"]


@mutation("a plant's margin changed")
def _(d):
    d["plants"][0]["margin"] = bump(d["plants"][0]["margin"], 5)


@mutation("a planted value changed in its 20th digit")
def _(d):
    row = plant(d, "P11")
    row["planted"] = bump(row["planted"], 20)


@mutation("a planted series changed (P2)")
def _(d):
    v = d["planted_series"]["P2"]["inv-F3"]["n_T_B"]["value"]
    v[3] = bump(v[3], 12)


@mutation("a planted series changed (P4)")
def _(d):
    v = d["planted_series"]["P4"]["inv-F1"]["n_U_K"]["value"]
    v[3] = bump(v[3], 30)


@mutation("a planted series changed (P7)")
def _(d):
    v = d["planted_series"]["P7"]["inv-H2|0.064453125"]["H_tot"]["value"]
    v[3] = bump(v[3], 12)


@mutation("a planted series changed (P15)")
def _(d):
    v = d["planted_series"]["P15"]["inv-eq-mid|0.15625"]["n_T_1"]["value"]
    v[0] = bump(v[0], 30)


@mutation("a planted series changed (P19, the middle step)")
def _(d):
    v = d["planted_series"]["P19"]["inv-J1|0.2578125"]["n_T_A"]["value"]
    v[3] = bump(v[3], 25)


@mutation("the planted series of a step-keyed plant keyed by world alone")
def _(d):
    table = d["planted_series"]["P11"]
    table["inv-F1L"] = table.pop("inv-F1L|8.25")


@mutation("an accuracy of zero on a value that is not zero")
def _(d):
    series(d, "inv-F1", "n_T_A")["accuracy"][3] = "0"


@mutation("an E entry that is not zero")
def _(d):
    series(d, "inv-F1", "n_T_K")["value"][0] = "1.000000000000000000000000000000000000000E-300"


@mutation("an exchange's heat changed in its 37th digit")
def _(d):
    block = d["events"]["inv-N-buffered"]
    block["heat"] = bump(block["heat"], 37)


@mutation("an exchange's sample taken after the refill")
def _(d):
    block = d["events"]["inv-N-buffered"]
    block["sample"] = block["before"]


@mutation("B_def changed in its 37th digit")
def _(d):
    case = d["cases"]["inv-eq-mid|0.078125"]
    case["B_def"] = bump(case["B_def"], 37)


@mutation("the retry's case missing")
def _(d):
    del d["cases"]["inv-eq-mid|0.0048828125"]


@mutation("a case too many")
def _(d):
    d["cases"]["inv-eq-mid|0.5"] = d["cases"]["inv-eq-mid|1.25"]


@mutation("the scheme's transfer given as the exact one")
def _(d):
    case = d["cases"]["inv-eq-mid|1.25"]
    case["m_R"] = case["m_star"]


@mutation("tag and plain swapped in B")
def _(d):
    s = d["worlds"]["inv-F1L"]["series"]
    s["label_T_tag_B"], s["label_T_plain_B"] = s["label_T_plain_B"], s["label_T_tag_B"]


@mutation("the output times shifted")
def _(d):
    d["worlds"]["inv-G1"]["times_s"] = d["worlds"]["inv-G1"]["times_s"][1:] + [7.0]


@mutation("the state after a portion at the portion's own row")
def _(d):
    v = series(d, "inv-G1", "n_T_K")["value"]
    v[2] = v[3]


@mutation("the exchange world's face heat in its twin after the exchange")
def _(d):
    series(d, "inv-N-none", "H_face")["value"][6] = series(d, "inv-N-buffered", "H_face")["value"][6]


@mutation("the inputs' hash")
def _(d):
    d["inputs_sha256"] = "0" * 64


@mutation("a check that fails")
def _(d):
    d["checks"][3]["passes"] = False


@mutation("the still face's total changed in its 22nd digit")
def _(d):
    v = series(d, "inv-J0", "H_tot")["value"]
    v[2] = bump(v[2], 22)


@mutation("the face beside the flow: its heat left out of the total")
def _(d):
    s = d["worlds"]["inv-J1"]["series"]
    s["H_tot"], s["H_face"] = s["H_face"], s["H_tot"]


@mutation("a portion's loss changed in its 30th digit")
def _(d):
    row = d["events"]["inv-G1"][1]
    row["loss"] = bump(row["loss"], 30)


@mutation("an engine plant's missing heat dropped")
def _(d):
    d["plants_reported"] = d["plants_reported"][:1]


@mutation("an engine plant's missing heat changed")
def _(d):
    row = d["plants_reported"][1]
    row["H_missing"][4] = bump(row["H_missing"][4], 9)


@mutation("the E plant's distance zero")
def _(d):
    plant(d, "P9")["distance"] = "0"


@mutation("the E plant given a margin of 1")
def _(d):
    plant(d, "P9").update({"margin": "1", "no_margin": False})


@mutation("a plant margin of 9")
def _(d):
    plant(d, "P15")["margin"] = "9.000000000000000000000000000000000000000E+0"


@mutation("a uniform stream's class made S")
def _(d):
    series(d, "inv-H5", "H_A")["class"][2] = "S"


@mutation("a class outside the six")
def _(d):
    series(d, "inv-H1", "H_A")["class"][2] = "N"


@mutation("a world without the prefix")
def _(d):
    d["worlds"]["F1"] = d["worlds"].pop("inv-F1")


@mutation("an extra world")
def _(d):
    d["worlds"]["inv-extra"] = d["worlds"]["inv-F1"]


@mutation("a value with fewer digits")
def _(d):
    v = series(d, "inv-F1", "n_T_A")["value"]
    v[3] = v[3][:20] + v[3][v[3].index("E"):]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--inputs", required=True)
    arguments = parser.parse_args()
    os.makedirs(arguments.scratch, exist_ok=True)
    shutil.copy(os.path.join(arguments.out, "inputs_invented.json"), arguments.scratch)
    with open(os.path.join(arguments.out, "reference_invented.json"), encoding="ascii") as handle:
        base = json.load(handle)

    def run(document):
        """The names of the rows that miss (or the exception's) on this document."""
        with open(os.path.join(arguments.scratch, "reference_invented.json"), "w", encoding="ascii") as handle:
            json.dump(document, handle)
        spec = importlib.util.spec_from_file_location("self_check_again", os.path.join(HERE, "self_check.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        saved = sys.argv
        sys.argv = ["self_check", "--out", arguments.scratch, "--inputs", arguments.inputs, "--only", "invented"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                module.main()
        except SystemExit:
            pass
        except Exception as error:                  # a malformed file that the check could not even read is a flag too
            return [f"exception {type(error).__name__}"]
        finally:
            sys.argv = saved
        return [row["name"] for row in module.ROWS if not row["passes"]]

    rows = []
    misses = run(copy.deepcopy(base))
    rows.append({"change": "none", "flagged": bool(misses), "first": misses[:1]})
    print("unchanged:", "clean" if not misses else misses[:2], flush=True)
    for name, function in MUTATIONS:
        document = copy.deepcopy(base)
        function(document)
        misses = run(document)
        rows.append({"change": name, "flagged": bool(misses), "first": misses[:1]})
        print("flagged" if misses else "MISSED ", name, flush=True)
    good = not rows[0]["flagged"] and all(row["flagged"] for row in rows[1:])
    with open(os.path.join(arguments.out, "mutation_tests.json"), "w", encoding="ascii") as handle:
        json.dump({"all_changes_flagged": all(row["flagged"] for row in rows[1:]), "changes": len(rows) - 1,
                   "unchanged_file_clean": not rows[0]["flagged"], "rows": rows}, handle, indent=1, sort_keys=True)
        handle.write("\n")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
