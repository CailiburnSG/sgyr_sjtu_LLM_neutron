"""Controlled vocabulary shared by event cards and evidence retrieval.

The values in this module are machine-facing labels.  They describe observable
signal patterns only; none is a diagnosis of a plant or instrument condition.
"""

from __future__ import annotations


EVENT_TAXONOMY_VERSION = "v1"

# Observable event patterns emitted by the current deterministic detector.
EVENT_TYPES = frozenset(
    {
        "short_zero",
        "sustained_zero",
        "positive_spike",
        "negative_drop",
        "upward_trend",
        "downward_trend",
        "transient_deviation",
    }
)

# Scope records how a final card was formed, not a physical relation.
EVENT_SCOPES = frozenset(
    {
        "single_channel",
        "multi_channel_temporal_cluster",
    }
)

# Optional labels for the operating context of an event or a reference window.
# They are deliberately separate from EVENT_TYPES: a stable signal alone cannot
# establish that the plant was in normal operation.
OPERATING_CONTEXTS = frozenset(
    {
        "normal_operation_confirmed",
        "steady_signal_baseline",
        "operating_transition_confirmed",
        "maintenance_or_test_confirmed",
        "operation_context_unknown",
    }
)

# Evidence-card applicability labels.  Kept ASCII-only for stable JSON and
# direct use in retrieval filters.
APPLICABILITY_TAGS = frozenset(
    {
        "data_qualification",
        "missing_data_check",
        "spike_data_qualification",
        "stuck_signal_screening",
        "historian_sampling_check",
        "channel_comparison",
        "neutron_current_channel_comparison",
        "neutron_current_temporal_comparison",
        "signal_path_context",
        "neutron_current_signal_path_context",
        "calibration_activity_check",
        "baseline_reference_selection",
        "neutron_current_measurement_context",
        "detector_response_time_context",
        "gamma_contribution_check",
        "detector_calibration_context",
        "signal_quality_context",
    }
)
