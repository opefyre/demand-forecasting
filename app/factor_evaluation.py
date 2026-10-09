"""Bounded factor-choice guardrails. Models/folds remain owned by forecast_engine."""
import math

POLICY = 'factor-selection-v1'
MIN_GAIN = .05
MAX_FACTORS = 8
NOTE = ('Choices use earlier test windows only. The final window is checked after '
        'the choice is frozen; it never changes the choice. Test-period factor '
        'values are held at the last training value. Future inputs are reviewed '
        'assumptions, not predicted facts. Release dates/revisions are not '
        'independently verified. No causal or future-accuracy guarantee.')


def choose_candidate(scores, factor_sets, eligible):
    """Select on earlier loss only, requiring a practical 5% improvement.

    Prefer a simpler factor set on exact ties. No confirmation scores enter here.
    Zero-demand windows use the engine's MAE rather than dividing by zero.
    """
    finite = {name: value for name, value in scores.items() if math.isfinite(value)}
    baseline = {name: value for name, value in finite.items() if not factor_sets[name]}
    if not baseline:
        raise ValueError('No complete history-only candidate was available. Review the history or method.')
    before = min(baseline, key=lambda name: (baseline[name], name))
    tested = {name: value for name, value in finite.items() if factor_sets[name]}
    candidate = min(tested, key=lambda name: (tested[name], len(factor_sets[name]), name)) if tested else None
    gain = ((finite[before] - finite[candidate]) / finite[before]) if candidate and finite[before] > 0 else 0.
    selected = candidate if eligible and candidate and gain >= MIN_GAIN else before
    return {'baseline_model': before, 'selected_model': selected,
            'selected_factors': list(factor_sets[selected]),
            'selection_baseline_loss': finite[before], 'selection_selected_loss': finite[selected],
            'selection_gain_pct': 100 * gain if selected == candidate else 0.,
            'decision': 'factors_selected' if selected == candidate else 'history_only',
            'reason': ('Earlier tests improved by at least 5%.' if selected == candidate else
                       'More complete test windows are needed.' if not eligible else
                       'No factor candidate cleared the 5% improvement guardrail.'),
            'candidate_count': len(scores), 'complete_candidates': len(finite)}
