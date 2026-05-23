# Sam Gamgee
**Sustainability Data Consultant | ESG Analytics | Data Architecture**

sam.gamgee@shire-consulting.co.uk | https://linkedin.com/in/samgamgee

---

## Core Skills

- Python *(Expert, 8 yr)*
- dbt *(Advanced, 4 yr)*
- PySpark *(Advanced, 5 yr)*
- Apache Airflow *(Advanced, 5 yr)*
- Apache Kafka *(Advanced, 5 yr)*
- Amazon Kinesis *(Intermediate, 3 yr)*
- BigQuery *(Intermediate, 3 yr)*
- Snowflake *(Intermediate, 3 yr)*
- Amazon Redshift *(Advanced, 5 yr)*
- Power BI *(Advanced, 4 yr)*
- Tableau *(Intermediate, 3 yr)*
- RDF / Turtle / SPARQL *(Expert, 6 yr)*
- Knowledge Graph Design *(Expert, 6 yr)*
- AWS (data services) *(Advanced, 6 yr)*
- Azure (data services) *(Intermediate, 2 yr)*
- Data Mesh & DataOps *(Advanced, 4 yr)*
- SFDR / PAI Indicators *(Expert, 4 yr)*
- TCFD Disclosure *(Advanced, 4 yr)*
- GRI Standards *(Advanced, 4 yr)*
- Carbon Accounting (GHG Protocol) *(Advanced, 4 yr)*
- Impact Measurement *(Advanced, 5 yr)*
- FHIR R4 (Health Informatics) *(Intermediate, 1 yr)*
- PostgreSQL *(Advanced, 6 yr)*
- scikit-learn *(Intermediate, 3 yr)*
- Flask *(Intermediate, 3 yr)*
- Terraform *(Intermediate, 3 yr)*
- AWS Glue *(Advanced, 4 yr)*
- SAP S/4HANA *(Intermediate, 2 yr)*
- HL7 v2 *(Intermediate, 1 yr)*

---

## Professional Experience

### Rivendell Health Systems
*Leeds | Health Informatics / NHS | February 2025 – present*

**Lead Data Architect**

Redesigning a regional NHS trust's integration architecture, moving from a custom HL7 v2 engine to a FHIR-native platform on Azure Health Data Services.

#### Clinical Data Pipeline Modernisation
*Lead Data Architect | February 2025 – present*

Redesigning a regional NHS trust's integration architecture from a custom HL7 v2 engine to a FHIR-native platform on Azure Health Data Services.

**Activities:**
Conducted current-state assessment of 38 system integrations and 120 daily message flows. Produced target-state FHIR R4 resource model and migration sequencing plan. Built a proof-of-concept ingesting ADT feeds at 99.97% fidelity.

**Outcomes:** Proof-of-concept demonstrated 99.97% fidelity for ADT feed ingestion, validating the target architecture for full programme roll-out.

*Skills: FHIR R4 (Health Informatics), Azure (data services), Python, HL7 v2*

*Sectors: healthcare*

---

### White Council Capital
*London & Zurich | Asset Management / Financial Services | February 2024 – November 2024*

**Sustainability Data Engineer**

Data engineering lead on the ESG reporting and analytics platform programme for White Council Capital (€18bn AUM asset manager), focused on SFDR Article 8 PAI disclosure, ESG data quality, and regulatory alignment.

#### ESG Reporting & Analytics Platform
*Sustainability Data Engineer | February 2024 – November 2024*

Design and build of a canonical ESG data platform for White Council Capital, enabling continuous SFDR Article 8 PAI disclosure and full audit traceability, replacing a 22-day manual reporting cycle.

**Activities:**
Built a canonical ESG data model covering 500+ indicators aligned to SFDR, GRI 300-series, and TCFD pillars as a Turtle RDF knowledge graph. Developed ingestion pipelines for nine data providers (Clarity AI, Bloomberg ESG, in-house portfolio system) orchestrated in Apache Airflow on AWS MWAA. Implemented a PySpark-based SFDR PAI calculation engine replacing a quarterly Excel workbook. Designed an automated data quality framework with 140 rules covering completeness, temporal consistency, plausibility, and cross-source reconciliation. Delivered self-service Power BI dashboards with row-level security for 35 portfolio managers and the compliance team.

**Outcomes:** Reporting cycle reduced from 22 days to 4 days. First SFDR PAI report produced three weeks ahead of regulatory deadline. Audit trail coverage increased from 41% to 100%. PAI calculation engine runtime reduced from four weeks (manual) to under four hours.

*Skills: Python, Apache Airflow, PySpark, AWS (data services), Amazon Redshift, RDF / Turtle / SPARQL, Knowledge Graph Design, Power BI, SFDR / PAI Indicators, TCFD Disclosure, GRI Standards, Impact Measurement*

*Sectors: finance*

---

### Mordor Industrial Group
*Manchester & Düsseldorf | Heavy Industry / Manufacturing | August 2022 – December 2023*

**Data Migration & Integration Lead**

Led the data and systems implementation stream for an SAP ECC to S/4HANA migration across seven UK and German sites for a European industrial manufacturer.

#### Supply Chain Resilience — SAP S/4HANA Migration
*Data Migration & Integration Lead | August 2022 – December 2023*

Data migration and systems integration stream for a European industrial manufacturer replacing SAP ECC with S/4HANA across seven UK and German sites following supply chain disruption.

**Activities:**
Designed and executed data migration strategy for 800 GB of transactional history and 2.3 million master data records across 22 test runs over 16 months. Built an ETL framework in Python and AWS Glue with automated reconciliation reporting. Delivered a real-time operational data platform (Kafka + Redshift) replacing four point-to-point batch interfaces. Developed a REST API integration layer connecting S/4HANA to three 3PL partners (DHL, DB Schenker, local UK carrier). Produced and coordinated a 72-hour cutover runbook spanning 17 technical workstreams and 40 engineers across two time zones.

**Outcomes:** All seven sites went live on schedule. Zero data integrity issues raised in 90-day hypercare. Planning system data latency reduced from overnight batch to under 90 seconds.

*Skills: Python, AWS Glue, Apache Kafka, Amazon Redshift, SAP S/4HANA, Terraform, AWS (data services)*

*Sectors: industry*

---

### Northern Energy Holdings
*Leeds | Energy & Utilities | January 2021 – June 2022*

**Data Platform Lead**

Owned data architecture and hands-on build of streaming platform and asset knowledge graph for a regional UK distribution network operator (1.2 million customers) under the Ofgem RIIO-ED2 price control.

#### Smart Grid Modernisation
*Data Platform Lead | January 2021 – June 2022*

Data platform underpinning the digital twin and demand-side response programme for a regional UK distribution network operator under the Ofgem RIIO-ED2 price control.

**Activities:**
Built real-time AMI meter data ingestion handling 6 TB/day at peak throughput of 200,000 events/second using Apache Kafka on AWS MSK feeding a Redshift analytical layer. Developed an asset knowledge graph in RDF/Turtle modelling 420,000 grid components with full spatial and topological relationships and SPARQL-based fault impact queries. Implemented PySpark data quality and anomaly detection jobs processing meter readings against historical baselines. Built a demand-side response data pipeline connecting 12,000 enrolled residential customers to SCADA/DMS for real-time flexibility dispatch.

**Outcomes:** Platform sustained full load without degradation throughout delivery. 14% improvement in outage duration (SAIDI). 60% reduction in fault diagnosis time via asset graph queries. Anomaly detection flagged ~0.8% erroneous readings before reaching dispatch systems.

*Skills: Apache Kafka, Amazon Kinesis, PySpark, Amazon Redshift, RDF / Turtle / SPARQL, Knowledge Graph Design, Python, AWS (data services)*

*Sectors: energy*

---

### Rohan Agricultural Cooperative
*York | Agriculture | June 2017 – February 2019*

**Data Engineer (Junior)**

Built a precision farming analytics platform for 340 cooperative members, integrating IoT field sensors, satellite imagery, and agronomic models.

#### Precision Farming Analytics Platform
*Data Engineer (Junior) | June 2017 – February 2019*

Precision farming analytics platform for 340 cooperative members integrating IoT field sensors, satellite imagery, and agronomic models.

**Activities:**
Built an MQTT-to-PostgreSQL ingestion pipeline for 1,200 in-field sensors. Developed a crop yield prediction model using scikit-learn (RMSE 8% below existing benchmarks). Built a farmer-facing reporting portal using Flask and Plotly, adopted by 160 members.

**Outcomes:** Participating farms reported 6% average yield improvement over two seasons. 160 cooperative members actively using the reporting portal.

*Skills: Python, PostgreSQL, scikit-learn, Flask*

*Sectors: environment*

---

## Education

**BSc (First Class Honours) – Computer Science**
*University of Leeds | Leeds | September 2014 – July 2017*


---

## Certifications & Training

- **AWS Certified Data Engineer – Associate** — Amazon Web Services — January 2023
- **Google Professional Data Engineer** — Google Cloud — January 2022
- **dbt Analytics Engineering Certification** — dbt Labs — January 2023
- **Databricks Certified Associate Developer for Apache Spark** — Databricks — January 2022

---

## Personal Projects

### rdflib Open-Source Contribution
*January 2023 – December 2023*

Contributor to the rdflib Python library, delivering Turtle serialiser bug fixes.

*Technologies: Python, RDF, Turtle serialisation*
*URL: https://github.com/RDFLib/rdflib*

### agri-etl-kit
*present*

Open-source ETL toolkit for agricultural data pipelines, published on GitHub with 220 stars.

*Technologies: Python, ETL, data pipelines, agriculture data*
*URL: https://github.com/samgamgee/agri-etl-kit*


---

## Publications

**RDF Knowledge Graphs for ESG Provenance**
*Open Data Science Conference, Edinburgh, March 2025*
> Speaker presentation exploring the use of RDF knowledge graphs to model provenance in ESG data platforms, with reference to SFDR and TCFD disclosure pipelines.


---
