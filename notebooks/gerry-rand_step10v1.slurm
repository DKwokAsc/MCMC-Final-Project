#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --mem=100gb
#SBATCH --time=24:00:00
#SBATCH --job-name=gerrychain_rand_10stepv1
#SBATCH --error=gerrychain_rand_10stepv1.%J.err
#SBATCH --output=gerrychain_rand_10stepv1.%J.out

module load anaconda
conda activate gerryenv
ipython -c "%run Wisconsin_MCMC_GerryChain_10stepv1.ipynb"
