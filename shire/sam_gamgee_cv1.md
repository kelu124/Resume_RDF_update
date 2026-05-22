# Sam Gamgee
**Data Engineering & Analytics Consultant**

Leeds, United Kingdom | sam.gamgee@shire-consulting.co.uk | +44 7700 900 222
LinkedIn: linkedin.com/in/samgamgee | GitHub: github.com/samgamgee

---

## Profile

Data engineering consultant with eight years of experience building production-grade data pipelines, analytics platforms, and knowledge graphs across energy, industrial, and public sector clients. Comfortable owning end-to-end architecture from ingestion to visualisation — and equally at home writing PySpark jobs and presenting architecture decisions to steering committees. Strong track record embedding within client teams and transferring skills to in-house engineers.

---

## Core Skills

**Engineering:** Python (pandas, PySpark, dbt, FastAPI), SQL (PostgreSQL, BigQuery, Snowflake), Apache Kafka, Airflow, dbt, Spark
**Infrastructure:** AWS (S3, Glue, Lambda, Redshift), Azure (ADF, Synapse), Terraform, Docker, Kubernetes
**Data & Ontologies:** RDF/Turtle, SPARQL, rdflib, knowledge graphs, data modelling, FAIR data principles
**Domains:** Energy & utilities, ESG/sustainability, industrial manufacturing, health informatics
**Methods:** Agile (Scrum/Kanban), data mesh, DataOps, CI/CD for data pipelines

---

## Professional Experience

### Shire Consulting Group — Senior Data Consultant
*Leeds | March 2020 – present*

---

#### White Council Capital — ESG Reporting & Analytics Platform
*February 2024 – November 2024 | Financial Services | London/Zurich*

**Sustainability Data Analyst & Engineer**

Data engineering lead within the ESG platform delivery programme managed by Frodo Baggins. Responsible for designing and building the data pipelines that fed the group's new regulatory-grade ESG reporting layer.

- Designed the canonical ESG data model (500+ indicators, aligned to SFDR, GRI, and TCFD schemas), including a Turtle RDF knowledge graph layer for provenance tracking
- Built ingestion pipelines for nine data sources (Clarity AI, Bloomberg ESG, internal portfolio system) using Apache Airflow on AWS MWAA
- Implemented automated data quality checks covering completeness, plausibility, and lineage — error rate fell from ~12 % to under 0.5 % at first downstream consumption
- Built the SFDR PAI calculation engine in PySpark, reducing compute cost by 60 % vs. the incumbent Excel-based process
- Delivered self-service dashboards in Power BI used by 35 portfolio managers from day one of go-live

*Skills: Python, Airflow, PySpark, AWS, RDF, ESG data modelling, SFDR, Power BI*

---

#### Mordor Industrial Group — Supply Chain Resilience Programme
*August 2022 – December 2023 | Heavy Industry | Manchester/Düsseldorf*

**Data & Systems Implementation Consultant**

Lead data engineer on the supply chain and ERP transformation programme led by Frodo Baggins, covering seven manufacturing sites in the UK and Germany.

- Designed the data migration strategy for 14 years of transactional history (~800 GB) from legacy SAP ECC to S/4HANA, including cleansing rules for 2.3 million master data records
- Built and maintained the ETL framework (Python + AWS Glue) used for 22 data migration runs during the project lifecycle
- Implemented a real-time operational data platform (Kafka + Redshift) feeding MES and planning systems post-go-live
- Created the integration layer between S/4HANA and three third-party logistics providers via REST APIs
- Owned the data cutover runbook, coordinating 17 technical workstreams across a 72-hour go-live window
- Outcomes: all seven sites went live on schedule; zero data integrity issues raised in the 90-day hypercare period

*Skills: SAP S/4HANA migration, AWS Glue, Kafka, Redshift, ETL, Python, data migration*

---

#### Northern Energy Holdings — Smart Grid Modernisation Programme
*January 2021 – June 2022 | Energy & Utilities | Leeds*

**Data Engineering Lead**

Senior data engineer on the smart grid modernisation programme led by Frodo Baggins. Built the real-time meter data platform and designed the asset knowledge graph that underpinned the grid digital twin.

- Architected and implemented a streaming ingestion pipeline handling 6 TB/day of AMI meter readings using Apache Kafka and AWS Kinesis
- Designed the asset knowledge graph in RDF/Turtle (using the cv: and custom cvx: extensions pattern) to model 420 000 grid assets, enabling complex SPARQL queries for fault propagation analysis
- Built automated data quality and anomaly detection jobs in PySpark, catching ~0.8 % of meter readings flagged as erroneous before downstream processing
- Developed the demand-side response data pipeline connecting 12 000 enrolled customers to the SCADA/DMS dispatch system
- Worked closely with programme lead Frodo Baggins on architecture decisions and Ofgem reporting datasets
- Outcomes: data platform processed peak load of 200 000 events/second without degradation; supported 14 % improvement in SAIDI

*Skills: Apache Kafka, Kinesis, PySpark, RDF/SPARQL, AWS, smart grid, real-time data*

---

### Brandybuck Data Solutions — Data Engineer
*Manchester | June 2017 – February 2020*

---

#### Rohan Agricultural Cooperative — Precision Farming Analytics Platform
*June 2017 – February 2019 | Agriculture | York*

**Junior / Mid Data Engineer**

First substantive project out of university. Built a precision farming analytics platform integrating IoT sensor data, satellite imagery, and agronomic models for a 340-member agricultural cooperative.

- Ingested data from 1 200 in-field sensors (soil moisture, temperature, yield monitors) via MQTT → PostgreSQL pipeline
- Built a crop yield prediction model (scikit-learn gradient boosting) achieving RMSE 8 % below the cooperative's existing advisory benchmarks
- Created a farmer-facing reporting portal in Flask/Plotly used by 160 members by end of season 2
- Outcomes: participating farms reported average yield improvement of 6 % over two seasons

*Skills: Python, PostgreSQL, MQTT, IoT, scikit-learn, Flask*

---

#### Gondor Municipal Authority — Infrastructure Monitoring & Reporting Platform
*March 2019 – February 2020 | Public Sector | Leeds*

**Data Engineer**

Designed and built an infrastructure monitoring and KPI reporting platform for a metropolitan local authority managing 4 200 assets (roads, bridges, drainage, street lighting).

- Consolidated asset condition data from eight legacy systems (CSV exports, REST APIs, GIS shapefiles) into a unified PostgreSQL data warehouse
- Built a dbt transformation layer producing 40 standardised KPI views used by asset managers and the Cabinet Member for Transport
- Developed geospatial analytics identifying 14 high-risk asset clusters, directly informing a £3.2 m capital investment decision
- Delivered the platform in 11 weeks (8 weeks ahead of original plan) by reusing an open-source dbt asset management template

*Skills: Python, dbt, PostgreSQL, GIS, geospatial analysis, public sector*

---

#### Rivendell Health Systems — Clinical Data Pipeline Modernisation
*February 2025 – present | Health Informatics | Leeds*

**Lead Data Architect**

Ongoing engagement to redesign the data integration architecture for a regional NHS trust. Scoping a move from a custom HL7 v2 integration engine to a FHIR-native platform (Azure Health Data Services).

- Completed a current-state assessment covering 38 system integrations and 120 daily message flows
- Designed target-state FHIR R4 resource model and migration sequencing plan
- Delivered proof-of-concept ingesting patient ADT feeds into FHIR at 99.97 % fidelity

*Skills: FHIR R4, Azure, HL7, health informatics, data architecture*

---

## Education

**BSc Computer Science (First Class Honours)** — University of Leeds, 2017
Final year project: *Distributed stream processing for agricultural IoT sensor networks*

---

## Certifications

- AWS Certified Data Engineer – Associate (2023)
- Google Professional Data Engineer (2022)
- dbt Analytics Engineering Certification (2023)
- Databricks Certified Associate Developer for Apache Spark

---

## Languages

English (native) · Dutch (conversational)

---

## Open Source

- Contributor to `rdflib` (minor fixes to the Turtle serialiser, 2023)
- Author of `agri-etl-kit`: lightweight ETL utilities for agricultural IoT data (GitHub, 220 stars)
