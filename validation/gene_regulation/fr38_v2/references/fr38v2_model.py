"""FR-38's second comparison, the code-blind references: each world's equations of motion.

Written from the spec folder alone (SPEC.md, LAWS.md, READOUTS.md, AMENDMENT-2026-11-24.md) and
the sheet sections LAWS.md names (docs/TEMPLATED_POLYMERISATION_LAWS.md at 707014e4: sections 0
to 2, 3.1, 3.2, 3.4, 4.1 to 4.8, 5.1's table and initial state, 9.1 to 9.8, 9.9's addendum, 9.12
readings 1-3 and 5-9, 9.14, 9.19 and 9.22).

The state is held in deviation form (SPEC.md section 3): each state is its change from its value
at t = 0, so a large row's small change keeps its digits. Arithmetic is numpy's long double (x86
80-bit extended precision, a 64-bit significand). The right-hand side is vectorised over a batch
of columns: each column is one row of a family (a run, a blank or a planted world), and a batch
may hold several copies of the family side by side (the integrators' stages).

Nothing here imports, runs or reads the engine.
"""

import numpy as np

import fr38v2_worlds as W

LD = np.longdouble
ONE = LD(1)
THOUSANDTH = ONE / LD(1000)
RT_KJ = LD(W.RT_J_PER_MOL) / LD(1000)       # kJ/mol: fl(R*T) in J/mol, divided by 1000
RT_J = LD(W.RT_J_PER_MOL)                   # J/mol (water's law, LAWS.md section 4)
COPY = LD(W.COPY_FMOL)
C_STD = LD(W.C_STANDARD_MM)


def ld(x):
    """A declared double (or small integer), exactly, as a long double."""
    return LD(x)


class Batch:
    """Per-column parameters for one batch width and one segment (a piecewise-constant span)."""


class World:
    """One family: its rows (runs, blank and planted worlds), state layout and right-hand side."""

    def __init__(self, fam):
        self.fam = fam
        self.name = fam["family"]
        self.arm = fam["arm"]
        self.store = fam["store"]
        self.water = fam["water"]
        self.inp = fam["inputs"]
        self.rows = fam["rows"]
        self.R = len(self.rows)
        self.row_index = {r["name"]: i for i, r in enumerate(self.rows)}
        self.plants = fam["plants"]
        self.has_blank = any(r["blank"] is not None for r in self.rows)
        self.p3 = ("P3a" in self.plants) or ("P3b" in self.plants)
        self.t1a = ld(self.plants.get("P3a", 0.0))
        self.t2b = ld(self.plants.get("P3b", 0.0))
        self._layout()
        self._parameters()
        self._initial_state()

    # ----------------------------------------------------------------------------------------
    def _layout(self):
        names = [f"C{j}" for j in range(1, 9)] + ["F", "H", "N", "M", "Pi", "R", "Rs"]
        if self.store:
            names += ["Mx"]
        if self.water:
            names += ["V"]
        if self.arm == "B":
            names += ["X", "A", "ATP", "ADP", "P", "Frib"]
            names += [f"Ctl{j}" for j in range(1, 9)] + [f"Ctls{j}" for j in range(1, 9)]
        names += ["iJI", "iS", "iQ", "iQd", "iQs", "iDR", "iDRs"]
        if self.arm == "B":
            names += ["iJItl", "iStl", "iQtl", "iJItls", "iStls", "iQtls", "iDP", "iJC"]
        names += ["Htx", "HdegR", "HdegRs", "HrelD", "HrelS"]
        if self.arm == "B":
            names += ["Htl", "HdegP", "Hrc"]
        if self.store:
            names += ["Hstore"]
        if self.water:
            names += ["Hwater", "Wbath"]
        for f in ("R", "Rs"):
            names += [f"{f}_pool0", f"{f}_resyn", f"{f}_pre", f"{f}_win", f"{f}_post"]
        names += ["netR", "netRs"]
        if self.p3:
            names += ["p3aR", "p3aRs", "p3bR", "p3bRs"]
        names += ["HW", "KR", "KRs"]
        if self.has_blank:
            names += ["XR", "XRs", "XM"]
            if self.store:
                names += ["XMx"]
            if self.water:
                names += ["XV"]
        self.names = names
        self.ix = {n: i for i, n in enumerate(names)}
        self.NS = len(names)

    # ----------------------------------------------------------------------------------------
    def _parameters(self):
        inp = self.inp
        if self.arm == "A":
            self.V0 = ld(inp["volume_pL"])
            self.L = ld(inp["L_residues"])
            self.m = int(inp["stages"])
            self.r = ld(inp["L_residues"] // inp["stages"])
            assert inp["L_residues"] % inp["stages"] == 0
            self.kappa = ld(inp["speed_nt_per_s"]) / self.r
            self.KN = ld(inp["K_N_mM"])
            self.Tc = ld(inp["template_copies"])
            self.Mpol = ld(inp["pool_machines_copies"]) * COPY
            self.tau = ld(inp["tau_s"])
            mu = inp["mu0_RT_at_1M"]
            self.muN, self.muM, self.muPi = ld(mu["N"]), ld(mu["M"]), ld(mu["Pi"])
            self.muR, self.muRs = ld(mu["R"]), ld(mu["R_s"])
            self.mures = ld(inp["mu_res_RT"])
            self.t1 = ld(inp["label_schedule_s"]["win"])
            self.t2 = ld(inp["label_schedule_s"]["post"])
            if self.store:
                st = inp["store"]
                self.muMx = ld(st["mu0_Mx_RT_at_1M"])
                # the D152 network's own potentials are equal for M and Mx, so the backward
                # factor exp(sum nu mu°/RT) is exactly 1 (LAWS.md section 3)
                assert st["network_mu0_RT_at_c0"]["M"] == st["network_mu0_RT_at_c0"]["Mx"]
                assert st["multiplier"] == 1.0
            if self.water:
                wa = inp["water"]
                assert wa["bulk_modulus_Pa"] == 0.0 and wa["pressure_offset_Pa"] == 0.0
                assert wa["impermeant_fmol"] == 0.0 and wa["bath_pressure_Pa"] == 0.0
                self.Vmin, self.Vmax = ld(wa["V_min_pL"]), ld(wa["V_max_pL"])
                self.nK = ld(inp["cell_background_mM"]["K"]) * self.V0
                self.nY = ld(inp["cell_background_mM"]["Y"]) * self.V0
                bath = (ld(inp["bath_mM"]["K"]) + ld(inp["bath_mM"]["Y"])
                        + 5 * ld(inp["bath_trace_mM"]))   # N, M, Pi, R and R_s traces
                self.psi_out = -RT_J * bath                 # Pa, with P_b = 0
                # Q = 1e15 A L_p a (psi_cell - psi_out), pL/s
                self.water_k = (LD(1e15) * ld(inp["patch_area_m2"]) * ld(wa["L_p_m_per_Pa_s"])
                                * ld(wa["availability"]))
        else:
            self.V0 = ld(inp["volume_pL"])
            self.L = ld(inp["L_R_nt"])
            self.m = int(inp["m_tx"])
            self.r = ld(inp["L_R_nt"] // inp["m_tx"])
            self.kappa = ld(inp["v_tx_nt_per_s"]) / self.r
            self.LP = ld(inp["L_P_aa"])
            self.rtl = ld(inp["L_P_aa"] // inp["m_tl"])
            self.kappa_tl = ld(inp["v_tl_aa_per_s"]) / self.rtl
            self.KN = ld(inp["K_N_tx_mM"])
            self.KA = ld(inp["K_A_tl_mM"])
            self.KATPtl = ld(inp["K_ATP_tl_mM"])
            self.VC = ld(inp["V_C_mM_per_s"])
            self.KMrc = ld(inp["K_M_rc_mM"])
            self.KATPrc = ld(inp["K_ATP_rc_mM"])
            self.kP = ld(inp["k_P_per_s"])
            self.KX = ld(inp["K_X_mM"])
            self.nXh = int(inp["n_X"])
            self.bX = ld(inp["b_X"])
            self.Pon = ld(inp["P_on_fmol_per_s"])
            self.kX = ld(inp["k_X_per_s"])
            self.toff = ld(inp["t_off_s"])
            self.kItl = ld(inp["k_I_tl_per_mM_s"])
            self.Tc = ld(inp["template_copies"])
            self.Mpol = ld(inp["M_pol_copies"]) * COPY
            self.Mrib = ld(inp["M_rib_copies"]) * COPY
            self.tau = ld(inp["tau_s"])
            mu = inp["mu0_RT_at_1M"]
            self.muN, self.muM, self.muPi = ld(mu["N"]), ld(mu["M"]), ld(mu["Pi"])
            self.muR, self.muRs = ld(mu["R"]), ld(mu["R_s"])
            self.muA, self.muATP, self.muADP = ld(mu["A"]), ld(mu["ATP"]), ld(mu["ADP"])
            self.muP = ld(mu["P"])
            self.mures = ld(inp["mu_res_R_RT"])
            self.muresP = ld(inp["mu_res_P_RT"])
            self.t1 = ld(inp["label_schedule_s"]["win"])
            self.t2 = ld(inp["label_schedule_s"]["post"])
        self.horizon = ld(inp["horizon_s"] if self.arm == "A" else inp["t_end_s"])
        # per-row parameters
        rows = self.rows
        self.kI = np.array([ld(r["k_I"]) for r in rows], dtype=LD)
        self.held = np.array([r["machine"] == "held" for r in rows])
        self.kR = np.array([ld(r["k_d"]) for r in rows], dtype=LD)
        self.kRs = np.array([ld(r["k_s"]) for r in rows], dtype=LD)
        self.kst = np.array([ld(r["k_store"]) for r in rows], dtype=LD)
        self.geneV0 = np.array([bool(r["gene_reads_V0"]) for r in rows])
        self.blank = np.array([self.row_index[r["blank"]] if r["blank"] is not None else -1
                               for r in rows], dtype=np.int64)
        for i, r in enumerate(rows):
            if r["blank"] is not None:
                b = self.rows[self.blank[i]]
                # a matched blank: every declaration equal but H(0) and k_I (erratum I, item 5)
                assert b["is_blank"] and b["k_d"] == r["k_d"] and b["k_s"] == r["k_s"]
                assert b["k_store"] == r["k_store"] and b["gene_reads_V0"] == r["gene_reads_V0"]

    # ----------------------------------------------------------------------------------------
    def _initial_state(self):
        I = self.ix
        y0 = np.zeros((self.NS, self.R), dtype=LD)
        inp = self.inp
        for i, r in enumerate(self.rows):
            H0 = ld(r["H0_copies"]) * COPY
            y0[I["H"], i] = H0
            y0[I["F"], i] = self.Mpol - (H0 if r["machine"] == "held" else LD(0))
            if self.arm == "A":
                c = inp["initial_mM"]
                y0[I["N"], i] = ld(c["N"]) * self.V0
                y0[I["M"], i] = ld(c["M"]) * self.V0
                y0[I["Pi"], i] = ld(c["Pi"]) * self.V0
                y0[I["R"], i] = ld(inp["initial_copies"]["R"]) * COPY
                y0[I["Rs"], i] = ld(inp["initial_copies"]["R_s"]) * COPY
                if self.store:
                    y0[I["Mx"], i] = ld(inp["store"]["Mx_initial_mM"]) * self.V0
                if self.water:
                    y0[I["V"], i] = self.V0
            else:
                c = inp["initial_mM"]
                for s in ("N", "M", "Pi", "X", "A", "ATP", "ADP", "P"):
                    y0[I[s], i] = ld(c[s]) * self.V0
                y0[I["R"], i] = ld(c["R"]) * self.V0
                y0[I["Rs"], i] = ld(c["R_s"]) * self.V0
                y0[I["Frib"], i] = self.Mrib
            y0[I["R_pool0"], i] = y0[I["R"], i]
            y0[I["Rs_pool0"], i] = y0[I["Rs"], i]
        self.y0 = y0

    # ----------------------------------------------------------------------------------------
    def switch_times(self):
        """Every time at which a piecewise-constant input changes (the solve restarts there)."""
        ts = {float(self.t1), float(self.t2)}
        for r in self.rows:
            for t, _ in r["p"]:
                ts.add(float(t))
        if self.p3:
            ts.add(float(self.t1a))
            ts.add(float(self.t2b))
        if self.arm == "B":
            ts.add(float(self.toff))
        return sorted(t for t in ts if 0.0 < t < float(self.horizon))

    def segment_values(self, t_start):
        """The piecewise-constant inputs in force on a span starting at t_start (a restart)."""
        t = float(t_start)
        sv = {}
        p = []
        for r in self.rows:
            val = None
            for ts, pv in r["p"]:
                if t >= ts:
                    val = pv
            p.append(ld(val))
        sv["p"] = np.array(p, dtype=LD)
        t1, t2 = float(self.t1), float(self.t2)
        sv["pre"] = ONE if t < t1 else LD(0)
        sv["win"] = ONE if (t1 <= t < t2) else LD(0)
        sv["post"] = ONE if t >= t2 else LD(0)
        if self.p3:
            sv["win_a"] = ONE if (float(self.t1a) <= t < t2) else LD(0)
            sv["win_b"] = ONE if (t1 <= t < float(self.t2b)) else LD(0)
        if self.arm == "B":
            sv["PX"] = self.Pon if t < float(self.toff) else LD(0)
        return sv

    def batch(self, copies, sv):
        """Column parameters for a batch of `copies` side-by-side copies of the family."""
        b = Batch()
        R = self.R
        b.W = copies * R
        b.y0 = np.tile(self.y0, (1, copies))
        b.kI = np.tile(self.kI, copies)
        b.held = np.tile(self.held, copies)
        b.kR = np.tile(self.kR, copies)
        b.kRs = np.tile(self.kRs, copies)
        b.kst = np.tile(self.kst, copies)
        b.geneV0 = np.tile(self.geneV0, copies)
        b.p = np.tile(sv["p"], copies)
        b.sv = sv
        if self.has_blank:
            offs = np.repeat(np.arange(copies, dtype=np.int64) * R, R)
            bl = np.tile(self.blank, copies)
            b.has_blank = bl >= 0
            b.bidx = np.where(b.has_blank, bl + offs, np.arange(b.W, dtype=np.int64))
        return b

    # ----------------------------------------------------------------------------------------
    def rhs(self, d, b):
        """d(state deviation)/dt for a batch: d has shape (NS, W)."""
        I = self.ix
        y = b.y0 + d
        out = np.zeros_like(d)
        sv = b.sv
        RT = RT_KJ
        L, r, kap = self.L, self.r, self.kappa

        if self.water:
            V = y[I["V"]]
            Vg = np.where(b.geneV0, self.V0, V)     # P9: the gene unit reads V0
        else:
            V = self.V0
            Vg = self.V0
        nN, nM, nPi = y[I["N"]], y[I["M"]], y[I["Pi"]]
        nR, nRs = y[I["R"]], y[I["Rs"]]
        Vc = Vg * C_STD
        lnaN = np.log(nN / Vc)
        lnaM = np.log(nM / Vc)
        lnaPi = np.log(nPi / Vc)
        lnaR = np.log(nR / Vc)
        lnaRs = np.log(nRs / Vc)
        F = y[I["F"]]
        H = y[I["H"]]
        C = y[I["C1"]:I["C1"] + 8]

        # initiation (sheet 4.1); B carries the regulator's factor u (sheet 4.6)
        cT = self.Tc * COPY / Vg
        if self.arm == "B":
            nX = y[I["X"]]
            cX = nX / V
            cX2 = cX * cX
            u = self.bX + (ONE - self.bX) * cX2 / (self.KX * self.KX + cX2)
            out[I["X"]] = sv["PX"] - self.kX * nX
            JI = u * b.kI * cT * F
        else:
            JI = b.kI * cT * F
        # elongation's stages, per-residue factor (sheet 4.2)
        x_tx = self.mures + 2 * (self.muPi + lnaPi) - (self.muN + lnaN)
        cN = nN / Vg
        phi = cN / (self.KN + cN) * (-np.expm1(x_tx))
        J = (kap * phi) * C
        S = J[0] + J[1] + J[2] + J[3] + J[4] + J[5] + J[6] + J[7]
        Qc = J[7]
        i1 = I["C1"]
        out[i1] = JI - J[0]
        out[i1 + 1:i1 + 8] = J[:-1] - J[1:]
        # the hold and the release (sheet 9.2, 9.3, 9.7)
        hr = H / self.tau
        Qd = b.p * hr
        Qs = (ONE - b.p) * hr
        out[I["H"]] = Qc - Qd - Qs
        out[I["F"]] = np.where(b.held, Qd + Qs, Qc) - JI
        # the fates' two-sided losses (sheet 4.4, 9.2; erratum I item 1)
        yR = self.muM + lnaM - (self.muR + lnaR) / L
        yRs = self.muM + lnaM - (self.muRs + lnaRs) / L
        eR = np.exp(yR)
        eRs = np.exp(yRs)
        DR = b.kR * nR * (-np.expm1(yR))
        DRs = b.kRs * nRs * (-np.expm1(yRs))
        out[I["R"]] = Qd - DR
        out[I["Rs"]] = Qs - DRs
        dM = L * (DR + DRs)
        dN = -r * S
        dPi = 2 * r * S
        # counters
        out[I["iJI"]] = JI
        out[I["iS"]] = S
        out[I["iQ"]] = Qc
        out[I["iQd"]] = Qd
        out[I["iQs"]] = Qs
        out[I["iDR"]] = DR
        out[I["iDRs"]] = DRs
        # heat classes (sheet 3.4, 9.5): each flux times its -dG
        out[I["Htx"]] = (r * S) * (-x_tx) * RT
        out[I["HdegR"]] = DR * (-L * yR) * RT
        out[I["HdegRs"]] = DRs * (-L * yRs) * RT
        out[I["HrelD"]] = Qd * (-lnaR) * RT
        out[I["HrelS"]] = Qs * (-lnaRs) * RT

        if self.arm == "B":
            nA, nATP, nADP, nP = y[I["A"]], y[I["ATP"]], y[I["ADP"]], y[I["P"]]
            lnaA = np.log(nA / Vc)
            lnaATP = np.log(nATP / Vc)
            lnaADP = np.log(nADP / Vc)
            lnaP = np.log(nP / Vc)
            Frib = y[I["Frib"]]
            x_tl = (self.muresP + 4 * (self.muADP + lnaADP) + 4 * (self.muPi + lnaPi)
                    - (self.muA + lnaA) - 4 * (self.muATP + lnaATP))
            cA = nA / V
            cATP = nATP / V
            phit = cA / (self.KA + cA) * (cATP / (self.KATPtl + cATP)) * (-np.expm1(x_tl))
            JItl = self.kItl * (nR / V) * Frib
            JItls = self.kItl * (nRs / V) * Frib
            Ct = y[I["Ctl1"]:I["Ctl1"] + 8]
            Cts = y[I["Ctls1"]:I["Ctls1"] + 8]
            Jt = (self.kappa_tl * phit) * Ct
            Jts = (self.kappa_tl * phit) * Cts
            St = Jt[0] + Jt[1] + Jt[2] + Jt[3] + Jt[4] + Jt[5] + Jt[6] + Jt[7]
            Sts = Jts[0] + Jts[1] + Jts[2] + Jts[3] + Jts[4] + Jts[5] + Jts[6] + Jts[7]
            Qt, Qts = Jt[7], Jts[7]
            it, its = I["Ctl1"], I["Ctls1"]
            out[it] = JItl - Jt[0]
            out[it + 1:it + 8] = Jt[:-1] - Jt[1:]
            out[its] = JItls - Jts[0]
            out[its + 1:its + 8] = Jts[:-1] - Jts[1:]
            out[I["Frib"]] = Qt + Qts - JItl - JItls
            yP = self.muA + lnaA - (self.muP + lnaP) / self.LP
            DP = self.kP * nP * (-np.expm1(yP))
            out[I["P"]] = Qt + Qts - DP
            rS = self.rtl * (St + Sts)
            out[I["A"]] = -rS + self.LP * DP
            dGrc = ((self.muN + lnaN) + 2 * (self.muADP + lnaADP) - (self.muM + lnaM)
                    - 2 * (self.muATP + lnaATP))
            cM = nM / V
            JC = (V * self.VC * (cM / (self.KMrc + cM)) * (cATP / (self.KATPrc + cATP))
                  * (-np.expm1(dGrc / 2)))
            dN = dN + JC
            dM = dM - JC
            dPi = dPi + 4 * rS
            out[I["ATP"]] = -4 * rS - 2 * JC
            out[I["ADP"]] = 4 * rS + 2 * JC
            out[I["iJItl"]] = JItl
            out[I["iStl"]] = St
            out[I["iQtl"]] = Qt
            out[I["iJItls"]] = JItls
            out[I["iStls"]] = Sts
            out[I["iQtls"]] = Qts
            out[I["iDP"]] = DP
            out[I["iJC"]] = JC
            out[I["Htl"]] = (rS * (-x_tl) + (Qt + Qts) * (-lnaP)) * RT
            out[I["HdegP"]] = DP * (-self.LP * yP) * RT
            out[I["Hrc"]] = JC * (-dGrc) * RT

        if self.store:
            nMx = y[I["Mx"]]
            # D152's passive law, M <-> Mx at equal potentials: J = m k_f (n_M - n_Mx), m = 1
            Jst = b.kst * (nM - nMx)
            dM = dM - Jst
            out[I["Mx"]] = Jst
            out[I["Hstore"]] = Jst * (np.log(nM) - np.log(nMx)) * RT

        if self.water:
            Sig = self.nK + self.nY + nN + nM + nPi + nR + nRs
            psi_cell = -RT_J * Sig / V
            dpsi = psi_cell - self.psi_out
            Qw = self.water_k * dpsi
            out[I["V"]] = -Qw
            out[I["Hwater"]] = THOUSANDTH * Qw * dpsi
            out[I["Wbath"]] = -THOUSANDTH * self.psi_out * Qw

        out[I["N"]] = dN
        out[I["M"]] = dM
        out[I["Pi"]] = dPi

        # the membership classes (LAWS.md section 1; erratum I item 2)
        for f, n, k, e, Q, ytag in (("R", nR, b.kR, eR, Qd, yR), ("Rs", nRs, b.kRs, eRs, Qs, yRs)):
            out[I[f + "_pool0"]] = -k * y[I[f + "_pool0"]]
            out[I[f + "_resyn"]] = k * n * e - k * y[I[f + "_resyn"]]
            out[I[f + "_pre"]] = Q * sv["pre"] - k * y[I[f + "_pre"]]
            out[I[f + "_win"]] = Q * sv["win"] - k * y[I[f + "_win"]]
            out[I[f + "_post"]] = Q * sv["post"] - k * y[I[f + "_post"]]
            # erratum I item 6: the net tracker (plant sizing only)
            out[I["net" + f]] = Q * sv["win"] - k * (-np.expm1(ytag)) * y[I["net" + f]]
            if self.p3:
                out[I["p3a" + f]] = Q * sv["win_a"] - k * y[I["p3a" + f]]
                out[I["p3b" + f]] = Q * sv["win_b"] - k * y[I["p3b" + f]]
        # P4: the window marked at completion; the hold's members that completed in W
        HW = y[I["HW"]]
        hw = HW / self.tau
        out[I["HW"]] = Qc * sv["win"] - hw
        out[I["KR"]] = b.p * hw - b.kR * y[I["KR"]]
        out[I["KRs"]] = (ONE - b.p) * hw - b.kRs * y[I["KRs"]]

        # the excess over the matched blank, integrated as its own difference states so that
        # the run's and the blank's common part cancels exactly (SPEC.md section 3, item 5)
        if self.has_blank:
            bb = b.bidx
            has = b.has_blank
            one_m = ONE - ONE / L
            XR, XRs, XM = d[I["XR"]], d[I["XRs"]], d[I["XM"]]
            nRb, nRsb, nMb = nR[bb], nRs[bb], nM[bb]
            lam_M = np.log1p(XM / nMb)
            if self.water:
                XV = d[I["XV"]]
                Vb = V[bb]
                lam_V = -one_m * np.log1p(XV / Vb)
            else:
                lam_V = LD(0)
            rho_Rb = nRb * eR[bb]
            rho_Rsb = nRsb * eRs[bb]
            d_rho_R = rho_Rb * np.expm1(one_m * np.log1p(XR / nRb) + lam_M + lam_V)
            d_rho_Rs = rho_Rsb * np.expm1(one_m * np.log1p(XRs / nRsb) + lam_M + lam_V)
            # D_f - D_f^blank = k (X - d_rho) + (k - k_blank)(n_blank - rho_blank)
            dDR = b.kR * (XR - d_rho_R) + (b.kR - b.kR[bb]) * (nRb - rho_Rb)
            dDRs = b.kRs * (XRs - d_rho_Rs) + (b.kRs - b.kRs[bb]) * (nRsb - rho_Rsb)
            zero = LD(0)
            out[I["XR"]] = np.where(has, Qd - Qd[bb] - dDR, zero)
            out[I["XRs"]] = np.where(has, Qs - Qs[bb] - dDRs, zero)
            dXM = L * (dDR + dDRs)
            if self.store:
                XMx = d[I["XMx"]]
                nMxb = y[I["Mx"]][bb]
                dJst = b.kst * (XM - XMx) + (b.kst - b.kst[bb]) * (nMb - nMxb)
                dXM = dXM - dJst
                out[I["XMx"]] = np.where(has, dJst, zero)
            out[I["XM"]] = np.where(has, dXM, zero)
            if self.water:
                Sigb = Sig[bb]
                XSig = ((d[I["N"]] - d[I["N"]][bb]) + XM + (d[I["Pi"]] - d[I["Pi"]][bb])
                        + XR + XRs)
                # Q - Q_blank = -water_k RT (Sig/V - Sig_b/V_b), written without cancellation
                dQw = -self.water_k * RT_J * (XSig / V - Sigb * XV / (V * Vb))
                out[I["XV"]] = np.where(has, -dQw, zero)
        return out
