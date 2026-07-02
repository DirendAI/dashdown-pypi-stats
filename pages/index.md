---
title: Explore a package
sidebar_position: 1
icon: 🔍
---

<Combobox name="project" data={project_options} column="name" label="Package" placeholder="Search a PyPI project — e.g. numpy, fastapi, rich" min_chars=2 url_sync bar />

# <span class="text-primary"><Value data={resolved} column="project" /></span> — PyPI downloads

Search any project to see how often it's pulled from PyPI, which versions and Python
runtimes use it, what installs it, and where in the world it's downloaded. Data comes
from the **free, public ClickHouse PyPI dataset** ([ClickPy](https://clickpy.clickhouse.com)) —
the official PyPI download logs, pre-aggregated and served for free. See
[About & data source](/about) for details.

Showing **<Value data={resolved} column="project" />** from
**<Value data={resolved} column="start_date" format="date" />** to
**<Value data={resolved} column="end_date" format="date" />**.
Quick picks:
[requests](/?project=requests) ·
[numpy](/?project=numpy) ·
[pandas](/?project=pandas) ·
[fastapi](/?project=fastapi) ·
[rich](/?project=rich) ·
[dashdown-md](/?project=dashdown-md)

## Key metrics

<Grid cols=5>
<Counter data={rank} column="rank" format="number" prefix="#" label="All-time rank" />
<Counter data={kpis} column="downloads" format="compact" label="Downloads" sparkline={daily} sparkline-column="downloads" />
<Counter data={kpis} column="avg_daily" format="compact" label="Avg / day" sparkline={daily_avg7} sparkline-column="avg7" />
<Counter data={kpis} column="versions" format="number" label="Versions seen" />
<Counter data={kpis} column="countries" format="number" label="Countries" />
</Grid>

> Raw counts include automated traffic (CI and mirrors). The **Installer** and
> **Operating system** charts below reveal the mix — watch how much comes from `uv`
> and Linux runners.

## About the package

**<Value data={pypi_meta} column="summary" />** — metadata from the free
[PyPI JSON API](https://docs.pypi.org/api/json/). Unlike the download charts, these
facts cover the package's whole life, so the period filter doesn't apply. Known
vulnerabilities count advisories against the latest release (PyPI's
[OSV](https://osv.dev) integration).

<Grid cols=5>
<Counter data={pypi_meta} column="latest_version" label="Latest version" />
<Counter data={pypi_meta} column="released" format="date" label="Last release" />
<Counter data={pypi_meta} column="total_releases" format="number" label="Releases (all time)" />
<Counter data={pypi_meta} column="dependencies" format="number" label="Runtime dependencies" />
<Counter data={pypi_meta} column="vulnerabilities" format="number" label="Known vulnerabilities" />
</Grid>

<Table data={pypi_facts} title="Package facts" />

## Downloads over time

<LineChart data={daily} x="day" y="downloads" title="Daily downloads" format="number" height={360} />

## Versions & file types

<Grid cols=2>
<BarChart data={by_version} x="version" y="downloads" title="Top versions" format="number" horizontal />
<PieChart data={by_filetype} x="file_type" y="downloads" title="Wheel vs source" donut />
</Grid>

## Install environment

<Grid cols=3>
<BarChart data={by_python} x="python_version" y="downloads" title="Python version" format="number" />
<PieChart data={by_installer} x="installer" y="downloads" title="Installer" donut />
<PieChart data={by_system} x="os" y="downloads" title="Operating system" donut />
</Grid>

## Where downloads come from

<BarChart data={by_country} x="country" y="downloads" title="Top countries" format="number" horizontal />

## Version detail

<Table data={version_detail} title="Downloads by version" format="downloads=number, share=percent" export />

## Release history

How often the project ships — every release ever published, from the PyPI JSON API
(not filtered by the period above).

<BarChart data={pypi_release_cadence} x="quarter" y="releases" title="Releases per quarter" format="number" height={280} />
