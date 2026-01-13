# Contest Log Analytics - User Guide

**Version: 1.2.0**
**Date: 2025-12-23**

---
### --- Revision History ---
## [1.2.0] - 2025-12-23
### Added
# - Added Multiplier Breakdown reports (HTML, Text, JSON) to Section 5.
## [1.1.0] - 2025-12-15
### Added
# - Added Section 6 "The Web Dashboard" to document the containerized workflow.
## [1.0.0] - 2025-12-06
### Added
# - Added `wrtc_propagation` and `wrtc_propagation_animation` to the list
#   of Available Reports.
## [0.94.0-Beta] - 2025-12-06
### Removed
# - Removed `multipliers_by_hour` from the list of Available Reports.
## [0.91.2-Beta] - 2025-10-11
### Changed
# - Updated the "Supported Contests" list to be a more user-friendly
#   conceptual list, rather than a list of specific CONTEST: tags.
# - Added the missing --wrtc <year> command-line option.
## [0.90.16-Beta] - 2025-10-06
### Added
# - Added the complete list of valid `CONTEST:` tags to Section 4.
# - Added a new subsection to Section 3 explaining the `<EventID>`
#   component of the output directory structure.
## [0.90.15-Beta] - 2025-10-06
### Fixed
# - Added the missing `CQ160mults.dat` file to the list of required
#   data files in Section 2.
# - Added the missing `--cty` argument to the list of command-line
#   options in Section 3.
## [0.88.4-Beta] - 2025-09-21
### Fixed
# - Synchronized the "Available Reports" list with the current project
#   baseline to add one missing report and correct one report ID.
## [0.86.8-Beta] - 2025-09-15
### Changed
# - Synchronized the "Available Reports" list to include the new WAE reports.
## [0.85.13-Beta] - 2025-09-13
### Changed
# - Added WAE CW and WAE SSB to the list of supported contests.
## [0.62.0-Beta] - 2025-09-08
### Changed
# - Updated documentation to reflect the new two-directory and two-environment-variable
#   system (CONTEST_INPUT_DIR and CONTEST_REPORTS_DIR).
## [0.56.31-Beta] - 2025-09-03
### Changed
# - Corrected the report ID for the QSO Breakdown Chart to align with the
#   source code.
## [0.56.30-Beta] - 2025-09-01
### Fixed
# - Added the missing `iaru_officials.dat` file to the list of
#   required data files.
## [0.55.0-Beta] - 2025-08-29
### Added
# - Added "IARU HF World Championship" to the list of supported contests.
## [0.54.3-Beta] - 2025-08-29
### Changed
# - Updated the --report argument and "Available Reports" list to
#   include all current report types and IDs.
## [0.40.2-Beta] - 2025-08-25
### Added
# - Added the required `band_allocations.dat` file to the list of
#   required data files in Section 2.
## [0.40.1-Beta] - 2025-08-24
### Added
# - Added the --debug-mults flag to the Command-Line Options list.
# - Added "ARRL Field Day" to the list of supported contests.
# - Added the 'chart_point_contribution' report to the list of available reports.
### Changed
# - Updated the description for SweepstakesSections.dat to include ARRL Field Day.
## [0.40.0-Beta] - 2025-08-19
### Changed
# - Updated the "Available Reports" list to be complete.
## [0.37.0-Beta] - 2025-08-18
### Changed
# - Aligned version with other documentation files.
# - Corrected the list of required data files in Section 2.
# - Updated the Command-Line Options list in Section 3 to include
#   the --debug-data flag.
## [0.36.8-Beta] - 2025-08-15
### Changed
# - Updated lists of required data files, CLI options, and supported
#   contests to be complete and accurate.
## [0.35.25-Beta] - 2025-08-15
### Changed
# - Updated the "Available Reports" list and the `--report` argument
#   description to be consistent with the current codebase.
## [0.30.31-Beta] - 2025-08-11
### Changed
# - Updated the "Available Reports" section to be complete and accurate
#   based on the current project state.
## [0.30.30-Beta] - 2025-08-05
# - Updated environment variable and --report argument documentation.
## [0.30.0-Beta] - 2025-08-05
# - Initial release of Version 0.30.0-Beta.
# - Standardized all project files to a common baseline version.

---

## 1. Introduction: What is the Contest Log Analytics?
The Contest Log Analytics is a powerful command-line tool designed for amateur radio contesters who want to perform deep, data-driven analysis of their operating performance.
It goes beyond the simple score summary provided by most logging software, allowing you to:

* Process raw Cabrillo log files into a clean, standardized format.
* Automatically classify every QSO as "Run," "Search & Pounce," or "Unknown" to analyze your operating strategy.
* Generate detailed reports and charts that compare your log against one or more others.
* Analyze performance on a band-by-band basis to identify strengths and weaknesses.
* Calculate contest-specific QSO points for supported contests.
The ultimate goal of this program is to help you understand your contest operation in minute detail, identify missed opportunities, and improve your strategy for the next event.
---

## 2. What You Need to Get Started

Before running the analyzer, you will need a few files and some configuration:

* **Your Cabrillo Log File(s)**: These are the standard log files generated by your contest logging software (e.g., `kd4d.log`, `n0ni.log`).
You can analyze a single log or compare multiple logs at once.
* **Data Files**: The program requires specific data files to be placed in a central `data/` directory.
* `cty.dat`: Required for all contests.
    * `arrl_10_mults.dat`: Required for the ARRL 10 Meter contest.
* `ARRLDXmults.dat`: Required for the ARRL DX contest.
    * `CQ160mults.dat`: Required for the CQ 160-Meter contest.
* `NAQPmults.dat`: Required for NAQP contests.
    * `SweepstakesSections.dat`: Required for ARRL Sweepstakes and ARRL Field Day.
* `band_allocations.dat`: Required for all contests to perform frequency validation.
    * `iaru_officials.dat`: Required for the IARU HF World Championship contest.
* **Environment Variables**: You must tell the program where to find your input files and where to save your output reports by setting two environment variables:
    * **`CONTEST_INPUT_DIR`**: This variable must point to the root directory that contains your `Logs` and `data` subdirectories.
This can be inside a cloud-synced folder like OneDrive.
    * **`CONTEST_REPORTS_DIR`**: This variable must point to the directory where the analyzer will create its `reports` output folder.
**This must be a local, non-synced path** (e.g., `C:\Users\YourUser\HamRadio\CLA`) to avoid file-locking errors.
---

## 3. How to Run the Analyzer

The program is run from your command prompt or terminal using `main_cli.py`.
#### **Basic Syntax**

    python main_cli.py --report <ReportID|all|chart|text|plot|animation|html> <LogFile1> [<LogFile2>...] [options]

#### **Command-Line Options**

* `--report <ReportID|all|chart|text|plot|animation|html>`: (Required) Specifies which report to generate.
Use a specific `ReportID` (e.g., `score_report`), `all` to generate every available report, or a category keyword like `chart` to run all chart reports.
* `<LogFile1> ...`: (Required) One or more paths to the Cabrillo log files you want to analyze.
The path should be relative to the `Logs` subdirectory in your `CONTEST_INPUT_DIR`.
* `--verbose`: (Optional) Enables detailed `INFO`-level status messages for debugging.
* `--include-dupes`: (Optional) By default, duplicate QSOs are ignored.
Use this flag to include them in all calculations.
* `--mult-name <name>`: (Optional) For reports that analyze multipliers (like `missed_multipliers`), this specifies which multiplier to use (e.g., 'Countries', 'Zones').
* `--metric <qsos|points>`: (Optional) For the `cumulative_difference_plots` report, this specifies whether to compare QSO counts or Point totals.
Defaults to 'qsos'.
* `--debug-data`: (Optional) When used with a visual report (chart, plot, animation), this saves the report's source data to a `.txt` file in a `Debug/` subdirectory.
* `--cty <specifier>`: (Optional) Specify the CTY file: 'before', 'after' (default), or a specific filename (e.g., 'cty-3401.dat').
* `--wrtc <year>`: (Optional) An optional argument to score IARU-HF logs using the rules for a specific WRTC year.
* `--debug-mults`: (Optional) Save intermediate multiplier lists from text reports for debugging.
#### **Examples**

* **Generate all available reports for two logs:**

```
python main_cli.py --report all 2025/cq-160-cw/kd4d.log 2025/cq-160-cw/n0ni.log
```

* **Generate only the text reports for two logs:**

```
python main_cli.py --report text 2025/cq-160-cw/kd4d.log 2025/cq-160-cw/n0ni.log
```

* **Generate a specific report (Score Summary) for a single log:**

```
python main_cli.py --report score_report 2025/cq-160-cw/kd4d.log
```

* **Generate a Missed Multipliers report for CQ WW Zones:**

```
python main_cli.py --report missed_multipliers --mult-name Zones 2024/cq-ww-cw/k3lr.log 2024/cq-ww-cw/kc1xx.log
```

---
### Understanding the Output Directory
The analyzer organizes reports into a structured directory path: `reports/<Year>/<ContestName>/<EventID>/<Callsigns>/`.
* **`<EventID>`**: For contests that run multiple times a year (like NAQP), this is a short identifier to separate the events.
For NAQP, this will be the three-letter month abbreviation (e.g., `JAN`, `FEB`, `AUG`). For other contests, this may be blank.
This structure ensures that reports from different events are kept separate.
---

## 4. Supported Contests

The analyzer uses the `CONTEST:` field in your Cabrillo file header to automatically apply the correct rules.
The following contests are currently supported:

* ARRL 10 Meter
* ARRL DX (CW & SSB)
* ARRL Field Day
* ARRL Sweepstakes
* CQ 160-Meter
* CQ WPX (CW & SSB)
* CQ World Wide DX (CW & SSB)
* IARU HF World Championship
* North American QSO Party (NAQP)
* WAE (CW & SSB)
* WRTC (via IARU-HF log and the `--wrtc` flag)

---

## 5. Available Reports

Use the `Report ID` with the `--report` command-line option.
#### **Animation Reports (`animations/`)**
* `hourly_animation`: Hourly Rate Animation
* `wrtc_propagation_animation`: WRTC Propagation Animation

#### **HTML Reports (`html/`)**
* `html_multiplier_breakdown`: Multiplier Breakdown Report (Group Par)
* `html_qso_comparison`: HTML QSO Comparison Report

#### **Chart Reports (`charts/`)**
* `chart_point_contribution`: Point Contribution Breakdown (Single Log)
* `qso_breakdown_chart`: QSO Breakdown Chart

#### **Plot Reports (`plots/`)**
* `band_activity_heatmap`: Band Activity Heatmap
* `comparative_band_activity`: Comparative Band Activity
* `comparative_band_activity_heatmap`: Comparative Band Activity Heatmap
* `comparative_run_sp_timeline`: Comparative Activity Timeline (Run/S&P)
* `cumulative_difference_plots`: Cumulative Difference Plot
* `point_rate_plots`: Cumulative Point Rate Plot
* `qso_rate_plots`: Cumulative QSO Rate Plot
* `wrtc_propagation`: WRTC Propagation by Continent

#### **Text Reports (`text/`)**
* `comparative_continent_summary`: Comparative Continent QSO Summary
* `text_multiplier_breakdown`: Multiplier Breakdown (Group Par)
* `rate_sheet_comparison`: Comparative Rate Sheet
* `comparative_score_report`: Comparative Score Report
* `continent_breakdown`: Continent Breakdown by Run/S&P
* `continent_summary`: Continent Summary
* `missed_multipliers`: Missed Multipliers
* `multiplier_summary`: Multiplier Summary
* `json_multiplier_breakdown`: JSON Multiplier Breakdown Artifact (Data Source)
* `qso_comparison`: QSO Comparison Summary
* `rate_sheet`: Hourly Rate Sheet (per hour)
* `score_report`: Score Report
* `summary`: QSO Summary by Run/S&P
* `text_wae_comparative_score_report`: WAE Comparative Score Report
* `text_wae_score_report`: WAE Score Summary

---
## License

This project is licensed under the **Mozilla Public License, v. 2.0**.
---

## 6. The Web Dashboard

The Contest Log Analytics now features a "Stateless" Web Interface designed for ease of use.

### Launching the App
1. Ensure Docker is running.
2. Navigate to the project root.
3. Run: `docker-compose up --build`
4. Open your browser to `http://localhost:8000`.

### Upload Options
The web dashboard supports flexible log analysis:
* **Single-Log Analysis:** Upload only Log 1 to analyze your performance, rates, and multipliers in detail.
* **Comparison Analysis (2-3 Logs):** Upload 2 or 3 logs to enable head-to-head comparison with unique vs. common QSO breakdowns.

### Identity Agnostic Workflow
The analyzer does not know "who you are." It simply compares logs.
* **Log 1:** Upload your primary log here (The "Hero"). This slot is required.
* **Log 2 & 3:** Upload competitor logs here (The "Villains"). These slots are optional.

### The Dashboard
Once analyzed, you are presented with a "Strategy Board":
* **The Scoreboard:** High-level metrics including Run % and total score.
* **The Triptych:** Three paths for deeper analysis (Animation, QSO Reports, Multiplier Reports).
* **Raw Data:** A button to download the full set of generated reports as a ZIP file.

### Single vs. Multi-Log Features
* **Single-Log Reports:** Score summaries, rate sheets, hourly breakdowns, multiplier analysis, and performance metrics.
* **Multi-Log Reports:** All single-log features plus cumulative difference plots, QSO comparison charts, missed multiplier analysis, and head-to-head rate comparisons.