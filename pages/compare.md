---
title: Compare packages
sidebar_position: 2
icon: ⚖️
---

<Combobox name="packages" data={project_options} column="name" label="Packages" placeholder="Add packages to compare — numpy, pandas, polars…" multi min_chars=2 url_sync bar />

# Comparing <span class="text-primary"><Value data={compare_resolved} column="packages" /></span>

Put up to six projects head-to-head over the selected period. Start typing to add
packages; leave it empty to fall back to the defaults (**numpy**, **pandas**, **polars**).
It reads the same pre-aggregated ClickHouse tables as the explorer, so the comparison is
just as fast — and just as free.

Comparing **<Value data={compare_resolved} column="packages" />** over
**<Value data={compare_resolved} column="start_date" format="date" />** to
**<Value data={compare_resolved} column="end_date" format="date" />**.

## Daily downloads

<LineChart data={compare_daily} x="day" y="downloads" series="project" title="Daily downloads" format="number" height={380} />

## Total downloads in period

<Grid cols=2>
<BarChart data={compare_totals} x="project" y="downloads" title="Total downloads" format="number" horizontal />
<PieChart data={compare_totals} x="project" y="downloads" title="Share of downloads" donut />
</Grid>

<Table data={compare_totals} title="Totals" format="downloads=number" export />

## Package metadata

Latest release, license, and lifetime stats for each selected package, from the free
[PyPI JSON API](https://docs.pypi.org/api/json/) — whole-of-life facts, so the period
filter doesn't apply here.

<Table data={compare_meta} title="Side by side" format="released=date, releases=number, dependencies=number, vulnerabilities=number" export />
