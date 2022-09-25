#!/bin/bash
#----------------------------------------------------
# Example SLURM job script to run OpenMP applications
# on TACC's Maverick system.
#----------------------------------------------------
#SBATCH -J job1                  			# Job name
#SBATCH -o log%j.out                        # Name of stdout output file(%j expands to jobId)
#SBATCH -p normal                   		# Submit to the 'normal' or 'development' queue
#SBATCH -N 1                        		# Total number of nodes requested 
#SBATCH -n 68                        		# Total number of mpi tasks requested
#SBATCH -t 5:00:00                 			# Run time (hh:mm:ss) - 5 hours
#SBATCH -A WebberEnergy         			# 'WebberEnergy' is the name of the project with the Stampede2 allocation
#SBATCH --mail-user=braden.pecora@austin.utexas.edu	        # email address to use
#SBATCH --mail-type=begin  	   				# email me when the job starts
#SBATCH --mail-type=end    	   				# email me when the job finishes

# all the stuff like you are sitting at the command line
# submit this script with sbatch TACC_shell.sh from the login node

source ~/miniconda3/etc/profile.d/conda.sh
conda activate HOwDI

export GUROBI_HOME="${HOME}/opt/gurobi950/linux64"
export PATH="${PATH}:${GUROBI_HOME}/bin"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${GUROBI_HOME}/lib"

cd "${HOME}/HOwDI/scenarios/base"
HOwDI monte_carlo