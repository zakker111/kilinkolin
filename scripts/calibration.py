"""Calibration helpers for attendance estimates.

Only a source that publishes realized attendance can produce a backtest error. The
Tampere city calendar publishes ``maxParticipants``, which is a capacity cap, not an
observed crowd; it is reported separately as coverage and never treated as ground truth.

The fit here is deliberately one parameter: a single fill factor for Liiga hockey. More
parameters on a twenty-game sample would look precise without being reliable.
"""
from __future__ import annotations

import statistics


def absolute_percentage_error(actual, predicted):
    if not isinstance(actual, (int, float)) or actual <= 0:
        return None
    return abs(predicted - actual) / actual


def fit_single_factor(samples, predict, prior, low=0.15, high=1.0, step=0.005):
    """Find the fill factor with the lowest mean absolute percentage error.

    ``samples`` are dicts with an ``actual`` value. ``predict(sample, factor)`` returns
    the model's mid estimate for that sample at the candidate factor. Ties go to the
    factor closer to the prior, so an unchanged model is preferred when the data cannot
    distinguish two candidates.
    """
    best = None
    factor = low
    while factor <= high + 1e-9:
        errors = [absolute_percentage_error(s["actual"], predict(s, factor)) for s in samples]
        errors = [e for e in errors if e is not None]
        if errors:
            score = sum(errors) / len(errors)
            candidate = (round(factor, 3), score)
            if best is None or score < best[1] - 1e-12 or (
                abs(score - best[1]) <= 1e-12
                and abs(candidate[0] - prior) < abs(best[0] - prior)
            ):
                best = candidate
        factor += step
    return best


def summarise(actuals, predictions):
    """Aggregate backtest errors and bias for one set of observations."""
    errors, signed = [], []
    for actual, predicted in zip(actuals, predictions):
        err = absolute_percentage_error(actual, predicted)
        if err is None:
            continue
        errors.append(err)
        signed.append((predicted - actual) / actual)
    if not errors:
        return None
    return {
        "sample": len(errors),
        "mape": round(sum(errors) / len(errors), 3),
        "median_ape": round(statistics.median(errors), 3),
        "bias": round(sum(signed) / len(signed), 3),
        "within_20pct": round(sum(e <= 0.20 for e in errors) / len(errors), 3),
    }


def leave_one_out(samples, predict, prior):
    """Fit on all but one observation, predict the held-out game, then aggregate.

    This is an honest in-sample-free error for a one-parameter model. It is still only
    as representative as the games in the sample, which is why the sample size and date
    range are published with the error.
    """
    if len(samples) < 3:
        return None
    actuals, predictions = [], []
    for i, held_out in enumerate(samples):
        train = samples[:i] + samples[i + 1:]
        fit = fit_single_factor(train, predict, prior)
        if not fit:
            continue
        actuals.append(held_out["actual"])
        predictions.append(predict(held_out, fit[0]))
    return summarise(actuals, predictions)
