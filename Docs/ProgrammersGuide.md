# Contest Log Analytics - Programmer's Guide

**Version: 0.129.0-Beta**
**Date: 2026-01-11**

---

## 1. Introduction & Architecture

The Contest Log Analytics project is built on three core architectural principles:

* **Data-Driven:** The behavior of the analysis engine is primarily controlled by data, not code. Contest rules, multiplier definitions, and parsing logic are defined in simple `.json` files.
* **Extensible:** The application uses a "plugin" architecture. New reports and contest-specific logic modules are dynamically discovered at runtime.
* **Convention over Configuration:** Files and classes must be named and placed in specific, predictable locations to be discovered.

---

## 2. The Data Abstraction Layer (DAL)

The `contest_tools.data_aggregators` package is the sole authority for data summarization. All Aggregators must return standard Python primitives (Dictionaries, Lists, Ints), not Pandas DataFrames.

### Primary Aggregators
* **`CategoricalAggregator`**: Handles set operations (Unique/Common QSOs) and categorical grouping.
* **`ComparativeEngine`**: Implements Set Theory logic to calculate Universe, Common, Differential, and Missed counts.
* **`MatrixAggregator`**: Generates 2D grids (Band x Time) for heatmaps.
* **`MultiplierStatsAggregator`**: Handles "Missed Multiplier" analysis and summarization.
* **`TimeSeriesAggregator`**: Generates the standard TimeSeries Data Schema (v1.4.0).
* **`WaeStatsAggregator`**: Specialized logic for WAE contests (QTCs and weighted multipliers).

---

## 3. Web Architecture (Phase 3)

The project includes a stateless, containerized web dashboard built on Django.

### The Manifest & WORM Strategy
To ensure responsiveness, the application employs a **"Write Once, Read Many" (WORM)** strategy.

1.  **Generation Phase:** During analysis, "Artifact Reports" (e.g., `json_multiplier_breakdown.py`) execute and serialize aggregation trees into JSON files.
2.  **Hydration Phase:** When a user loads a dashboard view, the view hydrates its context directly from these pre-computed JSON artifacts via the `ManifestManager`.
3.  **Result:** No re-parsing of Cabrillo logs occurs on page load.

---

## 4. Shared Utilities & Styles

* **`MPLStyleManager`**: Centralized Matplotlib styles for static plots.
* **`PlotlyStyleManager`**: Centralized Plotly styles for interactive visualizations.
    * `get_point_color_map()`: Standard color mapping for QSO points.
    * `get_qso_mode_colors()`: Standard scheme for Run/S&P modes.
* **`CtyManager`**: Manages the lifecycle and caching of the `cty.dat` country file.

---

## 5. How to Add a New Contest

To add a new contest (e.g., "My Contest"), you generally do not need to write Python code. You only need to define the rules in JSON.

### Step 1: Create the Definition
Create `contest_tools/contest_definitions/my_contest.json`.

### Step 2: Define Metadata
The `contest_name` must match the `CONTEST:` tag in the Cabrillo file header.

```json
{
  "contest_name": "MY-CONTEST",
  "dupe_check_scope": "per_band",
  "score_formula": "points_times_mults",
  "valid_bands": ["80M", "40M", "20M", "15M", "10M"]
}
```

### Step 3: Define Multipliers
Reference existing logic using the `inherits_from` key, or define custom logic.

```json
  "multiplier_rules": {
    "primary_mult": {
        "helper_type": "arrl_section"
    }
  }
```

### JSON Quick Reference
| Key | Description |
| :--- | :--- |
| `contest_name` | Matches the Cabrillo Header. |
| `score_formula` | Calculation logic (e.g., `points_times_mults`). |
| `cab_parser_module` | Optional: Name of a custom Python parser if standard parsing fails. |
| `inherits_from` | Inherit rules from another JSON file (e.g., `cq_ww_cw`). |