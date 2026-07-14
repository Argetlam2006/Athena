# 03_TECH_SPEC.md

# Athena Technical Architecture

Version: 1.0

Status: Approved

---

# Purpose

This document defines the complete engineering architecture for Athena Version 1.

It specifies

- overall system architecture
- engineering modules
- service boundaries
- data flow
- APIs
- deployment architecture
- implementation responsibilities

This document intentionally avoids business logic, which is defined by the Athena Intelligence Framework.

---

# System Overview

Athena is implemented as a layered analytical system.

Each layer has exactly one responsibility.

```

                    User

↓

────────────────────────────

Presentation Layer

↓

────────────────────────────

API Layer

↓

────────────────────────────

Decision Layer

↓

────────────────────────────

Athena Intelligence Framework

↓

────────────────────────────

Analytics Layer

↓

────────────────────────────

Machine Learning Layer

↓

────────────────────────────

SQL Warehouse

↓

────────────────────────────

ETL Pipeline

↓

────────────────────────────

Football Datasets

```

Each layer depends only on the layer below it.

No layer skips another.

---

# High-Level Architecture

```

                    Dashboard

Player Intelligence

Team Intelligence

Recruitment

Ask Athena

↓

FastAPI Backend

↓

Decision Engine

↓

Athena Intelligence Framework

↓

Analytics Engine

↓

Similarity Engine

↓

PostgreSQL Warehouse

↓

ETL Pipeline

↓

StatsBomb

FBref

Transfermarkt

```

---

# Module Responsibilities

Athena consists of eight independent modules.

---

## Module 1

Data Ingestion

Purpose

Collect football datasets.

Responsibilities

- Download datasets
- Parse raw files
- Validate schemas
- Store raw data

Output

Raw football data

---

## Module 2

ETL Pipeline

Purpose

Transform raw football data into structured relational data.

Responsibilities

Cleaning

Normalization

Deduplication

Identifier resolution

Validation

Warehouse loading

Output

Normalized SQL warehouse

---

## Module 3

SQL Warehouse

Purpose

Provide Athena's single source of truth.

Responsibilities

Store

Players

Teams

Matches

Events

Season Statistics

Transfer Data

Capability Scores

Recommendation Results

No AI-generated data is stored.

---

## Module 4

Analytics Engine

Purpose

Transform statistics into analytical features.

Responsibilities

Per-90 calculations

Percentiles

Normalization

Rolling averages

League normalization

Position normalization

Output

Feature vectors

---

## Module 5

Athena Intelligence Framework

Purpose

Convert analytical features into football intelligence.

Responsibilities

Capability generation

Player Intelligence

Team Intelligence

Decision Intelligence

Confidence estimation

Evidence generation

Output

Structured football knowledge

---

## Module 6

Machine Learning

Purpose

Support intelligent exploration.

Machine Learning does NOT replace analytics.

Responsibilities

Similarity Search

Player Clustering

Embedding Generation

Recommendation Ranking

Output

Similarity scores

Clusters

Candidate rankings

---

## Module 7

Decision Engine

Purpose

Answer football questions.

Inputs

User intent

↓

Player Intelligence

↓

Team Intelligence

↓

ML outputs

↓

Evidence

Outputs

Recommendations

Comparisons

Insights

Reports

Decision Types

Player Analysis

Team Analysis

Recruitment

Comparison

Every output must remain explainable.

---

## Module 8

AI Layer

Purpose

Translate structured intelligence into natural language.

Responsibilities

Scouting Reports

Executive Summaries

Player Comparison

Team Reports

Recruitment Reports

Important

The AI layer never performs analysis.

It communicates existing analysis.

---

# Presentation Layer

Athena consists of five workspaces.

Dashboard

Player Intelligence

Team Intelligence

Recruitment

Ask Athena

Each workspace consumes the same backend APIs.

---

# Data Flow

```

StatsBomb

↓

ETL

↓

Warehouse

↓

Analytics

↓

Athena Intelligence Framework

↓

Machine Learning

↓

Decision Engine

↓

FastAPI

↓

Dashboard

```

No component bypasses this flow.

---

# Technology Stack

Backend

Python

FastAPI

Data

PostgreSQL

Pandas

NumPy

Machine Learning

Scikit-Learn

Visualization

Plotly

Frontend

Streamlit

AI

OpenAI / Gemini API

---

# Backend Structure

backend/

ingestion/

etl/

warehouse/

analytics/

intelligence/

recommendation/

ai/

api/

utils/

Each folder contains one independent subsystem.

---

# API Design

Core endpoints

GET

/players

GET

/teams

GET

/player/{id}

GET

/team/{id}

POST

/recruitment/search

POST

/player/compare

POST

/team/analyze

POST

/athena/chat

GET

/dashboard

All responses use JSON.

---

# Data Contracts

Analytics Layer

↓

Produces Feature Vectors

Intelligence Layer

↓

Produces Capability Profiles

Decision Layer

↓

Produces Recommendations

AI Layer

↓

Produces Reports

Every layer communicates through structured objects.

Never through raw SQL queries.

---

# Performance Targets

Search

<500 ms

Recommendation

<2 seconds

Dashboard Load

<3 seconds

Similarity Search

<1 second

---

# Logging

Every module logs

Execution time

Warnings

Errors

Rows processed

Validation failures

Recommendation generation

Logs are centralized.

---

# Testing Strategy

Unit Tests

Analytics calculations

Capability calculations

Similarity calculations

API responses

Integration Tests

ETL

Warehouse

Recommendation pipeline

End-to-End Tests

Player search

Team analysis

Recruitment workflow

AI report generation

---

# Engineering Principles

Single Responsibility

Loose Coupling

High Cohesion

Reusable Components

Configuration over Hardcoding

Explainability

Deterministic Analytics

Modular Design

Every module should be replaceable without affecting unrelated systems.

---

# Version 1 Deliverables

Working ETL pipeline

PostgreSQL warehouse

Analytics engine

Athena Intelligence Framework

Similarity engine

Decision engine

Interactive dashboard

Player intelligence

Team intelligence

Recruitment intelligence

AI-generated reports

Documentation

GitHub repository

---

# Version 2 Extensions

The architecture is intentionally modular.

Future additions may include

Opponent Intelligence

Match Intelligence

Academy Intelligence

Contract Intelligence

Medical Intelligence

Live Match Analytics

Video Analytics

No architectural redesign should be required.

---

# Summary

Athena is engineered as a layered decision intelligence platform.

Each layer performs a single responsibility.

Every recommendation is derived from structured analytics, processed through the Athena Intelligence Framework and presented through explainable AI.

This architecture ensures that Athena remains scalable, maintainable and fully interpretable while supporting future expansion beyond recruitment into broader football intelligence.