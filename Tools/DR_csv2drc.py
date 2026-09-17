#!/usr/bin/env python3
# ------------------------------------------------------------
# TR-1um DRC v0.001
# Original version was made by jun1okamura from TokaiRika's document
# LICENSE: Apache License Version 2.0, January 2004,
#          http://www.apache.org/licenses/
#
# Usage:
#   ./DR_csv2drc.py ../libs.tech/klayout/drc/run.drc
# ------------------------------------------------------------

import sys
import csv

import io

# ------------------------------------------------------------
# Default files
# ------------------------------------------------------------

IFILE = "../Document/TR-1um_Drawing_Layer_DR_Table.csv"
HFILE = "./DR_csv2drc.head"

# ------------------------------------------------------------
# Translator
# ------------------------------------------------------------

L = {
    "WN(R)": "WR",
    "WN(C)": "WC",
    "WN(M)": "WN - WC - WR",
    "AN(C)": "AN & WC",
    "AN(R)": "AN & WR",
    "AN(T)": "ANT",
    "AP(T)": "APT",
    "AR(T)": "ART",
    "AR(S)": "AR",
    "AP+AR": "AP + AR",
    "AP+AC": "AP + AC",
    "AP+AN": "AP + AN",
    "AA+GC+GR": "AA + GC + GR",
    "AP+AN+AC+AR": "AA",
    "AP-GC": "AP - GC",
    "AN-GC": "AN - GC",
    "AP(M)": "AP - DP",
    "AN(M)": "AN - DN",
    "ARN(S)": "ARNS",
    "ARW(S)": "ARWS",
    "PMOS": "AP & GC - ESD",
    "NMOS": "AN & GC - ESD",
    "GC+GR": "GC + GR",
    "GC-AP": "GC - AP",
    "GC-AN": "GC - AN",
    "GA(CX)": "GA.not_covering(AC)",
    "GC(G)": "GC & AM",
    "GC(R)": "GC & WR",
    "GC(RR)": "GC & DLRR",
    "GR(S)": "GRS",
    "CO(L)": "CL",
    "CO(S)": "CS",
    "CO(C)": "CO & WC",
    "CO(CC)": "CO & AC",
    "CO(M)": "COM",
    "CO(B)": "CO & BGM",
    "CO(R)": "CO & WR",
    "CO(RR)": "CO & AR",
    "CO(RRN)": "CO & AR.covering(RRN)",
    "CO(RRW)": "CO & AR.covering(RRW)",
    "CO(RS)": "CR & GR",
    "CO(RSM)": "CRS",
    "CL(RR)": "CL & AR",
    "CO(RS)": "CO & GR",
    "CO(D)": "CO & AD",
    "M1(C)": "M1C",
    "M1(W)": "M1W",
    "V1(S)": "V1 - V1P",
    "V1(P)": "V1P",
    "Endcap": "Endcap",
    "Bevel": "Bevel",
    "TieDown": "TieDown",
    "RR(W)": "AR  - RR",
    "RS(W)": "GR  - RS",
    "RR(L)": "ARW - RR",
    "RS(L)": "RSW - RS",
    "APE": "MPE",
    "ANE": "MNE",
    "PMOSE": "MPE & GC",
    "NMOSE": "MNE & GC",
    "APE-GC": "MPE - GC",
    "ANE-GC": "MNE - GC",
    "GC-APE": "GC - MPE",
    "GC-ANE": "GC - MNE",
    "CO(E)": "COE",
    "CD(E)": "COD",
    "CS(E)": "COS",
    "V1(P)": "V1P",
    "M1(P)": "M1P",
    "M1(I)": "M1 - M1P - AC",
    "M1(S)": "M1S",
    "M2(P)": "M2P",
    "M2(I)": "M2 - M2P",
    "M2(S)": "M2S",
    "": "XXX",
}

# CSV function tokens are historically inconsistent in case.  Keep aliases
# explicit so that a source spelling change cannot silently alter semantics.
FUNC_CANONICAL = {
    token.casefold(): token
    for token in (
        "Prohibit",
        "Require",
        "Contain",
        "Exist",
        "Nmin",
        "Wmin",
        "Wmax",
        "Wfix",
        "Wmin/max",
        "Lmin/max",
        "Smin",
        "Smin/Smax",
        "Sfix",
        "Emin/max",
        "Emin",
        "Efix",
        "Fmin",
        "ECmin",
        "Rect",
        "Donut",
        "TieDown",
        "Ext",
        "ANTE",
        "XYmin",
    )
}
FUNC_CANONICAL["extw"] = "ExtW"


def normalize_func(func):
    token = "".join(func.split())
    try:
        return FUNC_CANONICAL[token.casefold()]
    except KeyError as exc:
        raise ValueError("unsupported DRC function token %r" % func) from exc


# ------------------------------------------------------------
# Print helpers
# ------------------------------------------------------------

def print_Zn(f, rule, func, L1, L2, L3, L4, min, max):
    match func:
        case "Prohibit":
            print(
                "((%-7s) & (%-7s)).output('%-5s:%2s over %2s')"
                % (L1, L2, rule, L4, L3),
                file=f,
            )
            return
        case "Require":
            print(
                "((%-7s) - (%-7s)).output('%-5s:%2s outside %s')"
                % (L1, L2, rule, L3, L4),
                file=f,
            )
            return
        case "Contain":
            print(
                "((%-7s).outside(%-6s)).output('%-5s:%2s without %s')"
                % (L1, L2, rule, L3, L4),
                file=f,
            )
            return

    raise ValueError("unsupported DRC function %r" % func)


Sn_OVERLAP_OK = ["WN.S2", "WN.S3", "WN.S4", "WN.AP", "WN.AN", "DP.AP", "DN.AN", "GA.AP", "GA.AN", "APE.CO", "ANE.CO", "V1.CL"] 
Sn_CROSS_NG = ["WN.AP", "WN.AN", "APE.CO", "ANE.CO"]

def print_Sn(f, rule, func, L1, L2, L3, L4, min, max):
    if L1 == L2:
        print(
            "(%-7s).drc(             space < %4.1f ).output('%-5s:%2s %s < %4.1f')"
            % (L1, min, rule, L3, func, min),
            file=f,
        )
        return
    elif rule == "M1.SW": # wide metal1 rule
        print(
            "(%-7s).space(%-4.1f).polygons.raw.interacting(%-7s).output('%-5s:%2s-%s %s < %4.1f')"
            % (L2, min, L1, rule, L3, L4, func, min),
            file=f,
        )
        return
    elif L3.startswith(L4) or rule.startswith("PO.M"): # Derived layers spacing to original layers
        print(
            "(%-7s).drc(sep(%-7s, transparent) < %4.1f ).output('%-5s:%2s-%s %s < %4.1f')"
            % (L1, L2, min, rule, L3, L4, func, min),
            file=f,
        )
        return
    else:
        print(
            "(%-7s).drc(      sep(%-7s) < %4.1f ).output('%-5s:%2s-%s %s < %4.1f')"
            % (L1, L2, min, rule, L3, L4, func, min),
            file=f,
        )
        if not (rule in Sn_OVERLAP_OK):
            print(
                "((%-7s) & (%-7s)                  ).output('%-5s:%2s overlap %s')"
                % (L1, L2, rule, L3, L4),
                file=f,
            )
        elif rule in Sn_CROSS_NG:
            print(
                "((%-7s).overlapping(%-7s).not_inside(%-7s)).output('%-5s:%2s overlap %s')"
                % (L2, L1, L1, rule, L3, L4),
                file=f,
            )


def print_MX(f, rule, func, L1, L2, L3, L4, min, max):
    rule_heading = ""
    match rule:
        case "AC.W1" | "CO.W1":
            print(
                "(%-7s).drc(           width <  %5.1f ).output('%-5s:%2s Wmin < %5.1f')"
                % (L1, min, rule, L3, min),
                file=f,
            )
            print(
                "(%-7s).drc(           width >  %5.1f ).output('%-5s:%2s Wmax > %5.1f')"
                % (L1, max, rule, L3, max),
                file=f,
            )
            return
        case "CR.W2":
            print(
                "(%-7s).drc(         bbox_max < %5.1f ).output('%-5s:%2s Lmin < %5.1f')"
                % (L1, min, rule, L3, min),
                file=f,
            )
            print(
                "(%-7s).drc(         bbox_max > %5.1f ).output('%-5s:%2s Lmax > %5.1f')"
                % (L1, max, rule, L3, max),
                file=f,
            )
            return
        case "GR.W1" | "AR.W1":
            rule_heading = "RES(W)"
            min_check = "Wmin"
            max_check = "Wmax"
        case "GR.L1" | "AR.L1":
            rule_heading = "RES(L)"
            min_check = "Lmin"
            max_check = "Lmax"
        case "AP.WM" | "AN.WM" | "APE.WM" | "ANE.WM":
            rule_heading = "MOS(W)"
            min_check = "Wmin"
            max_check = "Wmax"
        case "AP.LM" | "AN.LM" | "APE.LM" | "ANE.LM":
            rule_heading = "MOS(L)"
            min_check = "Lmin"
            max_check = "Lmax"

    if rule_heading:
        print("# ----- %s -----" % (rule_heading), file=f)
        print(
            "(%-7s).sep((%-7s), 0.1, projection, projecting < %5.1f ).output('%-5s:%2s %s < %5.1f')"
            % (L1, L2, min, rule, L3, min_check, min),
            file=f,
        )
        print(
            "(%-7s).sep((%-7s), 0.1, projection, projecting > %5.1f ).output('%-5s:%2s %s > %5.1f')"
            % (L1, L2, max, rule, L3, max_check, max),
            file=f,
        )
        print("# ", file=f)
        return

    raise ValueError("unsupported DRC rule/function combination: %s (%s)" % (rule, func))


# ------------------------------------------------------------
# Generate one DRC line
# ------------------------------------------------------------

def gen_drc(f, rule, func, L1, L2, L3, L4, min, max):
    match func:
        case "Prohibit" | "Require" | "Contain":
            print_Zn(f, rule, func, L1, L2, L3, L4, min, max)
            return
        case "Exist":
            print(
                "(%-7s).not_covering(%-5s).output('%-5s:%2s not_covering %2s')"
                % (L1, L2, rule, L4, L3),
                file=f,
            )
            return
        case "Nmin":
            print(
                "(%-7s).drc(             notch < %4.1f ).output('%-5s:%2s %s < %4.1f')"
                % (L1, min, rule, L3, func, min),
                file=f,
            )
            return
        case "Wmin":
            print(
                "(%-7s).drc(             width < %4.1f ).output('%-5s:%2s %s < %4.1f')"
                % (L1, min, rule, L3, func, min),
                file=f,
            )
            return
        case "Wmax":
            print(
                "(%-7s).sized(%.2f).sized(%.2f).output('%-5s:%2s %s > %4.1f')"
                % (L1, - max / 2.0, max / 2.0, rule, L3, func, max),
                file=f,
            )
            return
        case "Wfix":
            print(
                "(%-7s).drc(             width < %4.1f ).output('%-5s:%2s %s < %4.1f')"
                % (L1, min, rule, L3, func, min),
                file=f,
            )
            print(
                "(%-7s).drc(          bbox_min < %4.1f ).output('%-5s:%2s bbox_min < %4.1f')"
                % (L1, min, rule, L3, min),
                file=f,
            )
            print(
                "(%-7s).drc(          bbox_max > %4.1f ).output('%-5s:%2s bbox_max > %4.1f')"
                % (L1, min, rule, L3, min),
                file=f,
            )
            return
        case "Wmin/max" | "Lmin/max":
            print_MX(f, rule, func, L1, L2, L3, L4, min, max)
            return
        case "Smin":
            print_Sn(f, rule, func, L1, L2, L3, L4, min, max)
            return
        case "Smin/Smax":
            if rule in ["M1.SC"]:
                print(
                    "(%s).drc(bbox_max < %4.1f ).output('%-5s:%2s over %s %s < %4.1f')"
                    % (L1, min, rule, L4, L3, "Sfix", min),
                    file=f,
                )
                print(
                    "(%s).drc(bbox_max > %4.1f ).output('%-5s:%2s over %s %s > %4.1f')"
                    % (L1, max, rule, L4, L3, "Sfix", max),
                    file=f,
                )
                return
        case "Sfix":
            if rule in ["CO.SM", "COE.SE"]:
                print(
                    "(%-7s).drc(     sep(%-7s) < %4.1f ).output('%-5s:%2s-%s %s < %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
                print(
                    "(%-7s).not_interacting((%s_e + %s_s).raw, 2).output('%-5s:%2s-%s %s != %4.1f or off-center/missing %s')"
                    % (L2, L1, L1, rule, L3, L4, func, max, L3),
                    file=f,
                )
            elif rule in ["AR.GC"]:
                print(
                    "(%s.extents).drc(     sep(%-7s, projection) != %4.1f ).output('%-5s:%2s-%s %s != %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
                print(
                    "((%-7s) & (%-7s)                  ).output('%-5s:%2s overlap %s')"
                    % (L1, L2, rule, L3, L4),
                    file=f,
                )
            elif rule in ["CO.GG", "CDE.GC", "CSE.GC"]:
                print(
                    "(%-7s).drc(     sep(%-7s) < %4.1f ).output('%-5s:%2s-%s %s < %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
                print(
                    "(%s_ext%d - (%s_e + %s_s + %s).edges).output('%-5s:%2s-%s %s != %4.1f or off-center/missing %s')"
                    % (L2, int(min), L1, L1, L1, rule, L3, L4, func, min, L3),
                    file=f,
                )
            else:
                print(
                    "(%-7s).drc(     sep(%-7s) != %4.1f ).output('%-5s:%2s-%s %s != %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
            return

        case "Emin/max":
            print(
                "(%-7s).drc( enclosed(%-7s) < %4.1f ).output('%-5s:%2s-%s Emin < %4.1f')"
                % (L1, L2, min, rule, L3, L4, min),
                file=f,
            )
            print(
                "(%-7s).drc( enclosed(%-7s) > %4.1f ).output('%-5s:%2s-%s Emax > %4.1f')"
                % (L1, L2, max, rule, L3, L4, max),
                file=f,
            )
            return
        case "Emin":
            if rule in ["CR.AT", "COE.APT", "COE.ANT"]:
                print(
                    "(%-7s).edges.enclosed((%-7s), %4.1f, projection).output('%-5s:%2s-%s %s < %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
            else:
                print(
                    "(%-7s).drc( enclosed(%-7s) < %4.1f ).output('%-5s:%2s-%s %s < %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
            return
        case "Efix":
            if rule == "AC.GC":
                print(
                    "(%-7s).drc(enclosed(%-7s) != %4.1f ).output('%-5s:%2s-%s %s != %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
                return
            else:
                print(
                    "(%-7s).edges.not_interacting((%-7s).extended_in(%4.1f).edges).output('%-5s:%2s-%s %s != %4.1f')"
                    % (L1, L2, min, rule, L3, L4, func, min),
                    file=f,
                )
                return
        case "Fmin":
            print(
                "(%-7s).drc(enclosing(%-7s) < %4.1f ).output('%-5s:%2s-%s %s < %4.1f')"
                % (L1, L2, min, rule, L3, L4, func, min),
                file=f,
            )
            return
        case "ECmin":
            if rule in ["GC.E2"]:
                print("# ----- MOS(EndCap) -----", file=f)
                print(
                    "GC_EP_check = (%s & %s).drc( enclosed(%s, projection) < %4.1f).polygons"
                    % (L1, L2, L2, min),
                    file=f,
                )
                print(
                    "GC_EP_side = GC_EP_check.sep((%s - %s), 1.2+1.dbu, projection, only_opposite)"
                    % (L1, L2),
                    file=f,
                )
                print(
                    "GC_EP_check.interacting((GC_EP_check.edges & GC_EP_side.edges), 2 ..).output('%-5s:%2s Concave <= 1.2 Endcap < %4.1f')"
                    % (rule, L4, min),
                    file=f,
                )
                print("# ", file=f)
                return
        case "Rect":
            if max > 0:
                print_MX(f, rule, "Wmin/max", L1, L2, L3, L4, min, max)
            elif min > 0:
                print(
                    "(%-7s).drc(             width < %4.1f ).output('%-5s:%2s %s < %4.1f')"
                    % (L1, min, rule, L3, "Wmin", min),
                    file=f,
                )
            print(
                "(%-7s).non_rectangles.output('%-5s:%2s must be a rectangle')"
                % (L1, rule, L3),
                file=f,
            )
            return
        case "Donut":
            print("# ----- Surrounded -----", file=f)
            print(
                "(%-2s - (%-7s).holes                   ).output('%-5s:%2s must surrounded %s')"
                % (L1, L2, rule, L3, L4),
                file=f,
            )
            print("# ", file=f)
            return
        case "TieDown":
            print("# ----- TieDown -----", file=f)
            print(
                "((%-7s) - antenna_check((%-2s), GC, 0.0)).output('%-5s:%2s must tie down to %s')"
                % (L1, L2, rule, L3, L4),
                file=f,
            )
            print("# ", file=f)
            return
        case "Ext":
            print("# ----- Extended Pad Output Rule -----", file=f)
            print(
                "((%-7s).sized(%.1f, size_inside(%s), steps(%d)) - (%s).sized(-%.1f+1.dbu).sized(%.1f-1.dbu)).output('%-5s:%2s lead out must be %.1fum wide for %.1fum')"
                % (L1, min, L2, int(min), L2, max / 2.0, max / 2.0, rule, L3, max, min),
                file=f,
            )
            print("# ", file=f)
            return
        case "ANTE":
            print("# ----- Floating Gate -----", file=f)
            print(
                "( GC_FL_LBL_TOP ).output('%-5s:%2s must electrically connect to Substrate (or text if not chip level)')"
                % (rule, L3),
                file=f,
            )
            print("# ", file=f)
            return
        case "XYmin":
            print("# ----- Beveling -----", file=f)
            print(
                "(%-7s).drc( primary.edges.count != 8 ).output('%-5s:%2s shape NOT Octagon')"
                % (L1, rule, L3),
                file=f,
            )
            print(
                "(%-2s.extents - %2s).drc(       area < %4.2f ).output('%-5s:%2s trimmed corner size < %4.2f')"
                % (L1, L1, (min ** 2) / 2, rule, L3, (min ** 2) / 2),
                file=f,
            )
            print("# ", file=f)
            return

    raise ValueError("unsupported DRC rule/function combination: %s (%s)" % (rule, func))


# ------------------------------------------------------------
# Read one CSV row
# ------------------------------------------------------------

def validate_row(row, line_number):
    if not row or row[0] in {"", "#", "Rule"}:
        return

    if len(row) < 6:
        raise ValueError(
            "CSV line %d: expected at least 6 columns, got %d"
            % (line_number, len(row))
        )

    unresolved = [
        field
        for field, value in zip(("MIN", "MAX"), row[4:6])
        if value.strip() == "???"
    ]
    if unresolved:
        raise ValueError(
            "CSV line %d (%s): unresolved %s value(s)"
            % (line_number, row[0], ", ".join(unresolved))
        )

    normalize_func(row[3])
    try:
        if row[4] != "":
            float(row[4])
        if row[5] != "":
            float(row[5])
    except ValueError as exc:
        raise ValueError(
            "CSV line %d (%s): MIN/MAX must be numeric or blank"
            % (line_number, row[0])
        ) from exc


def read_line(f, row, line_number):
    validate_row(row, line_number)

    if not row or row[0] == "":
        return

    if row[0] == "#":
        print("# ----- ----- ----- ----- ----- ----- ----- ----- ", file=f)
        print("# NOTICE: THIS IS AUTO-GENERATED by DRC_csv2drc.py", file=f)
        print("# NOTICE: DO NOT EDIT DIRECTLY", file=f)
        print("# ----- ----- ----- ----- ----- ----- ----- ----- ", file=f)
        print("# %-s" % row[1], file=f)
        print("#", file=f)
        return

    if row[0] == "Rule":
        return

    rule = row[0].replace(" ", "")
    L3 = row[1].replace(" ", "")
    L4 = row[2].replace(" ", "")
    L1 = L[L3] if L3 in L else L3 # no longer need to define A = A
    L2 = L[L4] if L4 in L else L4 # no longer need to define A = A
    func = normalize_func(row[3])

    min = float(row[4]) if row[4] != "" else -1.0
    max = float(row[5]) if row[5] != "" else -1.0

    try:
        gen_drc(f, rule, func, L1, L2, L3, L4, min, max)
    except ValueError as exc:
        raise ValueError("CSV line %d (%s): %s" % (line_number, rule, exc)) from exc


# ------------------------------------------------------------
# Print header
# ------------------------------------------------------------

def print_head(ifile, ofile):
    head = ifile.read()
    print("%s" % head, file=ofile)

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    args = sys.argv

    if len(args) > 1:
        ofile = args[1]
    else:
        ofile = None

    with open(HFILE, "r", encoding="utf8") as head_file:
        head = head_file.read()

    with open(IFILE, "r", encoding="utf8", newline="") as csv_file:
        reader = csv.reader(
            csv_file,
            delimiter=",",
            doublequote=True,
            lineterminator="\r\n",
            quotechar='"',
            skipinitialspace=True,
        )
        rows = list(reader)

    # Validate before opening the output so a failed source row cannot leave
    # behind a truncated or partially generated runset.
    for line_number, row in enumerate(rows, start=1):
        validate_row(row, line_number)

    with io.StringIO() as generated:
        print("%s" % head, file=generated)
        for line_number, row in enumerate(rows, start=1):
            if row and row[0] != "":
                read_line(generated, row, line_number)
        content = generated.getvalue()

    if ofile is None:
        sys.stdout.write(content)
    else:
        with open(ofile, "w", encoding="utf8") as drc_file:
            drc_file.write(content)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(2)
