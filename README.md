# Wisconsin Gerrychain MCMC

This repository contains all code, data, and supporting files used for our final research project analyzing Wisconsin congressional redistricting using Markov Chain Monte Carlo (MCMC) methods. The project focuses on generating alternative districting plans, evaluating partisan outcomes, and analyzing metrics such as the efficiency gap and seat distributions.

The goal of this repository is to ensure reproducibility, transparency, and ease of exploration for anyone interested in computational redistricting or MCMC-based analysis.

# Project Overview

This project uses the GerryChain framework and Python-based data processing to:

- Generate ensembles of legally valid districting plans
- Simulate election outcomes on each plan
- Evaluate partisan fairness using efficiency gap and seat counts
- Study the effect of skipped steps (thinning) on MCMC convergence and stability

All data preprocessing, modeling, and analysis steps are documented and reproducible using the provided notebooks and helper scripts.

# Repository Structure
```
MCMC-Final-Project/
│
├── notebooks/
│   ├── *.ipynb
│   └── Description: Jupyter notebooks used to preprocess data,
│      run the Markov chains, and generate plots and results.
│      These notebooks are the primary entry point for reproducing
│      the analysis.
│
├── helper/
│   ├── *.py
│   └── Description: Helper scripts used to compute summary statistics
│      such as mean, variance, and standard deviation for the
│      generated ensembles.
│
├── data/
│   ├── *.xlsx
│   └── Description: Excel files containing pre-analysis data,
│      intermediate results, and supporting datasets used in
│      exploratory analysis.
│
├── README.md
└── .gitignore
```

# How to Reproduce the Results

### 1) Clone the repository
```
git clone https://github.com/your-username/MCMC-Final-Project.git
cd MCMC-Final-Project
```

### 2) Set up the Python environment

The project is written in Python and relies on common data science libraries as well as GerryChain. Recommended environment:

- Python 3.9+

- Jupyter Notebook or JupyterLab

Install required packages (example):

```
pip install numpy pandas matplotlib geopandas gerrychain
```

### 3) Run the notebooks

Navigate to the notebooks/ folder and run the notebooks in order. Each notebook contains markdown explanations describing its purpose and outputs.

OR

Run the documents in Google Collab. Be sure to follow the instructions in the notebooks folder.

# Data Sources

Wisconsin 2024 General Election Ward-Level Data

Source: Redistricting Data Hub

Original format: Shapefile (.shp)

Converted to JSON for graph-based modeling and MCMC simulations

All data included in this repository is used strictly for academic and research purposes.

# Notes

This repository is structured for academic replication, not production deployment.

Some notebooks may require significant runtime due to the computational cost of MCMC simulations.

Intermediate outputs are intentionally included to support transparency and debugging.

## Developed and Tested by
- **Jada L.** 
- **Daniel S.** 
- **David K.** — [GitHub Profile](https://github.com/DKwokAsc)
- **Omeed I.**  
- **Riley O.** 

Course: Math 435: Math in the City / Fall 2025

License

This project is intended for educational and research purposes only.
Please cite appropriately if you use or adapt this work.
