"""
============================================================================
 The Purple Cup - Email A/B Test (two-proportion z-test)
============================================================================
 SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.
 The experiment below is an additional simulated campaign for The Purple Cup.
 The data is invented; the experiment design and statistics are real.
 Author: Erica Mathias
----------------------------------------------------------------------------
 THE EXPERIMENT
   The Purple Cup emails a promotion with two subject-line variants:
     A (control)   : "Your matcha ritual, 10% off today"
     B (treatment) : "A little purple surprise inside"
   Every recipient is RANDOMLY assigned to A or B (a coin flip). Random
   assignment is what makes the groups equivalent in every way except the
   subject line, so a difference in conversion can be credited to the subject
   line rather than to who happened to land in each group.

   We then ask: is B's conversion rate genuinely higher, or could the gap be
   chance? We answer with a two-proportion z-test and report the p-value
   honestly.

 WHAT A p-VALUE IS (one honest sentence)
   The p-value is the probability of seeing a difference at least this large
   IF the two variants were truly identical; a small p-value means such a gap
   would be unlikely by luck alone, so we judge the difference to be real.
   (It is NOT the probability that B is better, nor the probability we are wrong.)
============================================================================
"""

from __future__ import annotations

import numpy as np
from scipy import stats

# --- Experiment configuration ----------------------------------------------
SEED = 42
RNG = np.random.default_rng(SEED)

N_RECIPIENTS = 12_000          # total emails sent, split randomly across A/B
TRUE_RATE_A = 0.028            # the (unknown-to-us) real conversion rates that
TRUE_RATE_B = 0.038            # the simulation draws from; the test must recover
ALPHA = 0.05                   # significance threshold (95% confidence)

VARIANT_A = 'A: "Your matcha ritual, 10% off today"'
VARIANT_B = 'B: "A little purple surprise inside"'


# ---------------------------------------------------------------------------
# 1. RUN THE EXPERIMENT  (random assignment, then observe conversions)
# ---------------------------------------------------------------------------
def run_experiment() -> dict:
    """
    Randomly assign each recipient to A or B, then simulate whether they
    convert based on their variant's true rate. Returns the OBSERVED counts -
    the only thing a real analyst would actually get to see.
    """
    # Coin-flip assignment. Groups come out near-equal but not exactly - which
    # is itself realistic and worth noting.
    assignment = RNG.choice(["A", "B"], size=N_RECIPIENTS)

    is_a = assignment == "A"
    n_a, n_b = int(is_a.sum()), int((~is_a).sum())

    # Simulate conversions: one weighted coin flip per recipient.
    conv_a = int((RNG.random(n_a) < TRUE_RATE_A).sum())
    conv_b = int((RNG.random(n_b) < TRUE_RATE_B).sum())

    return {"n_a": n_a, "x_a": conv_a, "n_b": n_b, "x_b": conv_b}


# ---------------------------------------------------------------------------
# 2. THE TWO-PROPORTION Z-TEST  (computed from the formula; SciPy for the p)
# ---------------------------------------------------------------------------
def two_proportion_ztest(x_a: int, n_a: int, x_b: int, n_b: int) -> dict:
    """
    Test whether conversion rates p_a and p_b differ.

    Under the null hypothesis "the two rates are equal," we pool both groups to
    estimate the shared rate, compute the standard error of the difference, and
    form a z-statistic (how many standard errors apart the two rates are). SciPy
    turns z into a two-sided p-value via the normal distribution.
    """
    p_a = x_a / n_a
    p_b = x_b / n_b

    # Pooled rate under the null, and the standard error it implies.
    p_pool = (x_a + x_b) / (n_a + n_b)
    se_pooled = np.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))

    z = (p_b - p_a) / se_pooled
    p_value = 2 * stats.norm.sf(abs(z))          # two-sided

    # 95% confidence interval for the true difference (unpooled SE for the CI).
    se_diff = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    z_crit = stats.norm.ppf(1 - ALPHA / 2)
    diff = p_b - p_a
    ci_low, ci_high = diff - z_crit * se_diff, diff + z_crit * se_diff

    return {
        "p_a": p_a, "p_b": p_b,
        "abs_diff": diff,
        "rel_lift": diff / p_a,
        "z": z, "p_value": p_value,
        "ci_low": ci_low, "ci_high": ci_high,
    }


def chi_square_crosscheck(x_a: int, n_a: int, x_b: int, n_b: int) -> float:
    """
    Independent sanity check: a chi-square test on the 2x2 table
    (converted / not) x (A / B) must agree with the z-test - in fact z**2 == chi2.
    Returns the chi-square p-value.
    """
    table = np.array([[x_a, n_a - x_a], [x_b, n_b - x_b]])
    chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
    return p


# ---------------------------------------------------------------------------
# 3. REPORT
# ---------------------------------------------------------------------------
def main() -> None:
    exp = run_experiment()
    res = two_proportion_ztest(exp["x_a"], exp["n_a"], exp["x_b"], exp["n_b"])
    chi_p = chi_square_crosscheck(exp["x_a"], exp["n_a"], exp["x_b"], exp["n_b"])

    print("\n" + "=" * 70)
    print(" THE PURPLE CUP - EMAIL A/B TEST  (SIMULATED DATA)")
    print("=" * 70)
    print(f"\n{VARIANT_A}")
    print(f"{VARIANT_B}")
    print("\nRandom assignment split the send into two groups:")
    print("-" * 70)
    print(f"  {'Variant':<9}{'Sent':>10}{'Converted':>12}{'Conv. rate':>14}")
    print(f"  {'A':<9}{exp['n_a']:>10,}{exp['x_a']:>12,}{res['p_a']:>13.2%}")
    print(f"  {'B':<9}{exp['n_b']:>10,}{exp['x_b']:>12,}{res['p_b']:>13.2%}")

    print("\nTWO-PROPORTION Z-TEST")
    print("-" * 70)
    print(f"  Absolute difference : {res['abs_diff']*100:+.2f} percentage points")
    print(f"  Relative lift       : {res['rel_lift']:+.1%} (B vs A)")
    print(f"  95% CI (difference) : [{res['ci_low']*100:+.2f}, {res['ci_high']*100:+.2f}] pts")
    print(f"  z-statistic         : {res['z']:.3f}")
    print(f"  p-value (two-sided) : {res['p_value']:.4f}")
    print(f"  chi-square cross-check p : {chi_p:.4f}   (should match the z-test)")

    significant = res["p_value"] < ALPHA
    verdict = "STATISTICALLY SIGNIFICANT" if significant else "NOT statistically significant"

    print("\n" + "=" * 70)
    print(" CONCLUSION")
    print("=" * 70)
    if significant:
        print(
            f"- Variant B lifted conversion from {res['p_a']:.1%} to {res['p_b']:.1%}, a "
            f"{res['rel_lift']:.0%} relative increase (p = {res['p_value']:.4f}).\n"
            f"  The result is {verdict} at the {int((1-ALPHA)*100)}% level: a gap this large\n"
            f"  would be unlikely if the two subject lines were truly equally good, so we\n"
            f"  conclude B genuinely outperforms A. Recommend rolling out subject line B."
        )
    else:
        print(
            f"- Variant B's rate ({res['p_b']:.1%}) is higher than A's ({res['p_a']:.1%}), but the\n"
            f"  result is {verdict} (p = {res['p_value']:.4f}). We cannot rule out chance;\n"
            f"  we would collect more data before switching subject lines."
        )
    print(
        "\n- Honest reading of the p-value: it is the chance of a difference at least\n"
        "  this big IF the variants were identical - not the probability B is better."
    )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
