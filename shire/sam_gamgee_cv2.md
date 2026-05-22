# Sam Gamgee
**Sustainability Data Consultant | ESG Analytics | Data Architecture**

Leeds, United Kingdom | sam.gamgee@shire-consulting.co.uk | +44 7700 900 222
LinkedIn: linkedin.com/in/samgamgee

---

## Summary

Data consultant specialising in sustainability reporting, ESG data platforms, and knowledge graph architectures. Eight years of experience turning fragmented environmental, social, and governance data into audit-ready, regulatory-grade outputs. Delivered ESG data programmes for asset managers, energy networks, and industrial manufacturers. Particular expertise in SFDR/TCFD disclosure pipelines, RDF-based provenance modelling, and embedding data quality frameworks inside fast-moving delivery programmes.

---

## Areas of Expertise

| ESG & Sustainability | Data Engineering | Architecture |
|---|---|---|
| SFDR (PAI indicators) | Python, dbt, PySpark | RDF / Turtle / SPARQL |
| TCFD disclosure | Apache Airflow | Knowledge graph design |
| GRI Standards | Kafka, Kinesis | AWS / Azure (data services) |
| Carbon accounting (GHG Protocol) | BigQuery, Snowflake, Redshift | Data mesh & DataOps |
| Impact measurement | Power BI, Tableau | FHIR (health informatics) |

---

## Selected Projects

---

### ESG Reporting & Analytics Platform — White Council Capital
*Financial Services | London & Zurich | February 2024 – November 2024*
**Role: Sustainability Data Engineer**

White Council Capital, an asset manager with €18 bn AUM, needed to meet SFDR Article 8 PAI disclosure obligations and move from a manual 22-day reporting cycle to a continuous, auditable data process.

I joined the programme (Programme Manager: Frodo Baggins) as the data engineering lead with specific focus on ESG data quality and regulatory alignment.

**What I built:**
- A canonical ESG data model spanning 500+ indicators, aligned simultaneously to SFDR, GRI 300-series, and TCFD pillars, stored as a Turtle RDF knowledge graph for full provenance traceability
- Ingestion pipelines for nine external and internal data providers (Clarity AI, Bloomberg ESG, in-house portfolio system), orchestrated in Apache Airflow on AWS MWAA
- A PySpark-based SFDR PAI calculation engine — replaced an Excel workbook that took a team of three analysts four weeks per quarter; new engine runs in under four hours with full audit trail
- Automated data quality framework: 140 rules covering completeness, temporal consistency, plausibility, and cross-source reconciliation; error rate at first consumption: 0.4 %
- Self-service Power BI dashboards with row-level security for 35 portfolio managers and the compliance team

**Impact:** Reporting cycle cut from 22 days to 4 days; first SFDR PAI report produced three weeks ahead of regulatory deadline; 100 % audit trail coverage vs. 41 % previously.

*Technologies: Python, Airflow, PySpark, AWS (MWAA, S3, Redshift), RDF/Turtle, Power BI, Clarity AI API*

---

### Smart Grid Modernisation — Northern Energy Holdings
*Energy & Utilities | Leeds | January 2021 – June 2022*
**Role: Data Platform Lead**

A regional UK distribution network operator (1.2 million customers) was upgrading its grid infrastructure under the Ofgem RIIO-ED2 price control. The data platform underpinning the digital twin and demand-side response programme was a critical dependency across all four delivery workstreams.

Working alongside Programme Lead Frodo Baggins, I owned the data architecture and hands-on build of the streaming platform and asset knowledge graph.

**What I built:**
- Real-time AMI meter data ingestion handling **6 TB/day** at peak throughput of 200 000 events/second — Apache Kafka on AWS MSK feeding a Redshift-based analytical layer
- An asset knowledge graph in RDF/Turtle modelling 420 000 grid components (substations, feeders, meters, switches) with full spatial and topological relationships, enabling SPARQL-based fault impact queries that replaced manual GIS lookups
- Data quality and anomaly detection jobs (PySpark) processing each meter reading against historical baselines — flagged ~0.8 % erroneous readings before they reached dispatch systems
- Demand-side response data pipeline connecting 12 000 enrolled residential customers to SCADA/DMS, supporting real-time flexibility dispatch

**Impact:** Platform sustained full load without degradation throughout delivery; contributed to a 14 % improvement in outage duration (SAIDI); asset graph queries drove a 60 % reduction in fault diagnosis time.

*Technologies: Apache Kafka, AWS MSK, Kinesis, PySpark, Redshift, RDF/SPARQL, rdflib, Python*

---

### Supply Chain Resilience — Mordor Industrial Group
*Heavy Industry | Manchester & Düsseldorf | August 2022 – December 2023*
**Role: Data Migration & Integration Lead**

A European industrial manufacturer was replacing its legacy SAP ECC landscape with S/4HANA across seven UK and German sites following supply chain disruption. The data and systems implementation stream was a critical path dependency; I led it within the broader programme run by Frodo Baggins.

**What I delivered:**
- Data migration strategy and execution framework for 800 GB of transactional history and 2.3 million master data records — 22 migration test runs over 16 months before production cutover
- ETL framework in Python and AWS Glue, with automated reconciliation reporting comparing source and target record counts, financial balances, and open orders at every run
- Real-time operational data platform (Kafka + Redshift) feeding MES and planning systems, replacing four point-to-point batch interfaces with a unified streaming layer
- REST API integration layer connecting S/4HANA to three 3PL partners (DHL, DB Schenker, local UK carrier)
- Data cutover runbook for a 72-hour go-live window, coordinating 17 technical workstreams and 40 engineers across two time zones

**Impact:** All seven sites live on schedule; zero data integrity issues raised in 90-day hypercare; planning system data latency fell from overnight batch to under 90 seconds.

*Technologies: Python, AWS Glue, Kafka, Redshift, SAP S/4HANA, REST APIs, Terraform*

---

### Precision Farming Analytics — Rohan Agricultural Cooperative
*Agriculture | York | June 2017 – February 2019*
**Role: Data Engineer (Junior)**

Built a precision farming analytics platform for 340 cooperative members, integrating IoT field sensors, satellite imagery, and agronomic models.

- MQTT → PostgreSQL ingestion pipeline for 1 200 in-field sensors
- Crop yield prediction model (scikit-learn) — RMSE 8 % below existing benchmarks
- Farmer-facing reporting portal (Flask / Plotly) used by 160 members
- Outcome: participating farms reported 6 % average yield improvement over two seasons

*Technologies: Python, PostgreSQL, MQTT, scikit-learn, Flask*

---

### Clinical Data Pipeline Modernisation — Rivendell Health Systems
*Health Informatics | Leeds | February 2025 – present*
**Role: Lead Data Architect**

Redesigning a regional NHS trust's integration architecture: moving from a custom HL7 v2 engine to a FHIR-native platform on Azure Health Data Services.

- Current-state assessment: 38 system integrations, 120 daily message flows
- Target-state FHIR R4 resource model and migration sequencing plan
- Proof-of-concept ingesting ADT feeds at 99.97 % fidelity

*Technologies: FHIR R4, Azure Health Data Services, Python, HL7*

---

## Education

**BSc Computer Science (First Class Honours)** — University of Leeds, 2017

---

## Certifications

- AWS Certified Data Engineer – Associate (2023)
- Google Professional Data Engineer (2022)
- dbt Analytics Engineering Certification (2023)
- Databricks Certified Associate Developer for Apache Spark (2022)

---

## Professional Engagement

- Speaker, *"RDF knowledge graphs for ESG provenance"* — Open Data Science Conference, Edinburgh, March 2025
- Contributor: `rdflib` open-source library (Turtle serialiser fixes, 2023)
- Author: `agri-etl-kit` open-source ETL toolkit (GitHub, 220 stars)
