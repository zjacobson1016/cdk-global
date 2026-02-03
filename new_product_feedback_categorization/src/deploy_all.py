#!/usr/bin/env python3
"""
Convergence-Based Deployment Orchestrator

This script uses an iterative convergence approach:
1. Deploy bundle (failures OK)
2. Run setup scripts (failures OK)
3. Run pipeline and jobs
4. Deploy Databricks App (sync files + deploy)
5. Repeat steps 1-4 until everything succeeds (convergence)

The system tracks what fails/succeeds across iterations and converges
to a fully deployed state by retrying until all components are successful.

Usage:
    python deploy_all.py --target dev
    python deploy_all.py --target prod --max-iterations 5
"""

import subprocess
import sys
import argparse
import time
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

# Get the project root directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# State file to track completed operations
STATE_FILE = PROJECT_ROOT / ".deployment_state.json"

# Use the venv's databricks CLI (has auth configured)
# The venv CLI is configured with the necessary authentication
import shutil
VENV_DATABRICKS = PROJECT_ROOT.parent / ".venv" / "bin" / "databricks"
if VENV_DATABRICKS.exists():
    DATABRICKS_CLI = str(VENV_DATABRICKS)
else:
    # Fall back to PATH
    DATABRICKS_CLI = shutil.which("databricks")
    if not DATABRICKS_CLI:
        raise RuntimeError("Databricks CLI not found. Please install it or activate your virtual environment.")


class ConvergenceDeployment:
    """Orchestrates deployment using convergence approach - iterate until everything succeeds."""
    
    def __init__(self, target: str = "dev", max_iterations: int = 5, verbose: bool = False,
                 skip_completed: bool = True, reset_state: bool = False):
        self.target = target
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.skip_completed = skip_completed
        
        # Track results across all iterations
        self.iteration_results: List[Dict[str, List[Tuple[str, bool]]]] = []
        self.current_iteration = 0
        
        # Track what has succeeded at least once
        self.ever_succeeded: Dict[str, bool] = defaultdict(bool)
        
        # Load previous state
        self.state = self._load_state()
        if reset_state:
            self.state = {"completed": {}, "last_updated": {}}
            self._save_state()
    
    def _load_state(self) -> Dict:
        """Load deployment state from file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Could not load state file: {e}")
        return {"completed": {}, "last_updated": {}}
    
    def _save_state(self):
        """Save deployment state to file."""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save state file: {e}")
    
    def _mark_completed(self, step: str):
        """Mark a step as completed."""
        self.state["completed"][step] = True
        self.state["last_updated"][step] = datetime.now().isoformat()
        self._save_state()
    
    def _is_completed(self, step: str) -> bool:
        """Check if a step has been completed."""
        return self.state.get("completed", {}).get(step, False)
        
    def run_command(self, command: List[str], name: str, step: str) -> bool:
        """
        Run a command and return success status.
        
        Args:
            command: Command to run
            name: Human-readable name
            step: Step name for tracking
            
        Returns:
            True if successful, False otherwise
        """
        print(f"\n{'─'*70}")
        print(f"🚀 {name}")
        print(f"{'─'*70}")
        print(f"Command: {' '.join(command)}\n")
        
        try:
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                check=False,  # Don't raise on non-zero exit
                capture_output=not self.verbose,
                text=True
            )
            
            if not self.verbose and result.stdout:
                # Show output but filter noise
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Error' in line or 'Failed' in line or '✓' in line or '✗' in line:
                        print(line)
            
            success = result.returncode == 0
            
            if success:
                print(f"✅ {name} - SUCCESS")
                self.ever_succeeded[step] = True
            else:
                print(f"❌ {name} - FAILED (exit code: {result.returncode})")
                if not self.verbose and result.stderr:
                    print(f"Error: {result.stderr[:200]}")  # Show first 200 chars of error
            
            return success
            
        except Exception as e:
            print(f"❌ {name} - EXCEPTION: {str(e)}")
            return False
    
    def step1_bundle_deploy(self) -> bool:
        """Step 1: Deploy Databricks bundle."""
        print(f"\n{'='*70}")
        print("📦 STEP 1: BUNDLE DEPLOYMENT")
        print(f"{'='*70}")
        print("Deploying all resources via databricks bundle deploy")
        print("This includes:")
        print("  • Volumes, schemas, and databases")
        print("  • DLT pipelines")
        print("  • Jobs and workflows")
        print("  • Model serving endpoints (may take ~10 min)")
        print("  • Dashboards and apps")
        print("  • Quality monitors")
        print("\n(Some failures are expected in early iterations)")
        print("(Long-running resources like serving endpoints deploy asynchronously)\n")
        
        command = [DATABRICKS_CLI, "bundle", "deploy", "-t", self.target]
        return self.run_command(command, "Bundle Deploy", "bundle_deploy")
    
    def step2_run_all_setup(self) -> bool:
        """Step 2: Run all setup scripts."""
        print(f"\n{'='*70}")
        print("🔧 STEP 2: SETUP SCRIPTS")
        print(f"{'='*70}")
        print("Running all setup scripts via run_all_setup")
        print("(Some failures are expected in early iterations)\n")
        
        command = [DATABRICKS_CLI, "bundle", "run", "run_all_setup", "-t", self.target]
        return self.run_command(command, "Setup Scripts", "setup_scripts")
    
    def step3_run_pipeline(self) -> bool:
        """Step 3a: Run DLT pipeline."""
        step_name = "pipeline"
        
        # Check if already completed
        if self.skip_completed and self._is_completed(step_name):
            print(f"\n{'='*70}")
            print("📊 STEP 3a: RUN PIPELINE")
            print(f"{'='*70}")
            print("✅ Pipeline already completed successfully - SKIPPING")
            last_run = self.state.get("last_updated", {}).get(step_name, "unknown")
            print(f"   Last successful run: {last_run}\n")
            return True
        
        print(f"\n{'='*70}")
        print("📊 STEP 3a: RUN PIPELINE")
        print(f"{'='*70}")
        print("Executing DLT pipeline\n")
        
        command = [DATABRICKS_CLI, "bundle", "run", "zach-demo_pipeline", "-t", self.target]
        result = self.run_command(command, "DLT Pipeline", step_name)
        
        if result:
            self._mark_completed(step_name)
        
        return result
    
    def step3_run_sql_job(self) -> bool:
        """Step 3b: Run SQL job (Create Metric View)."""
        step_name = "sql_job"
        
        # Check if already completed
        if self.skip_completed and self._is_completed(step_name):
            print(f"\n{'='*70}")
            print("📝 STEP 3b: RUN SQL JOB")
            print(f"{'='*70}")
            print("✅ SQL Job already completed successfully - SKIPPING")
            last_run = self.state.get("last_updated", {}).get(step_name, "unknown")
            print(f"   Last successful run: {last_run}\n")
            return True
        
        print(f"\n{'='*70}")
        print("📝 STEP 3b: RUN SQL JOB")
        print(f"{'='*70}")
        print("Executing SQL job (Create Metric View)\n")
        
        command = [DATABRICKS_CLI, "bundle", "run", "run_sql", "-t", self.target]
        result = self.run_command(command, "SQL Job (Create Metric View)", step_name)
        
        if result:
            self._mark_completed(step_name)
        
        return result
    
    def step3_run_ml_job(self) -> bool:
        """Step 3c: Run ML model training job."""
        step_name = "ml_job"
        
        # Check if already completed
        if self.skip_completed and self._is_completed(step_name):
            print(f"\n{'='*70}")
            print("🤖 STEP 3c: RUN ML JOB")
            print(f"{'='*70}")
            print("✅ ML Job already completed successfully - SKIPPING")
            last_run = self.state.get("last_updated", {}).get(step_name, "unknown")
            print(f"   Last successful run: {last_run}\n")
            return True
        
        print(f"\n{'='*70}")
        print("🤖 STEP 3c: RUN ML JOB")
        print(f"{'='*70}")
        print("Executing ML model training job\n")
        
        command = [DATABRICKS_CLI, "bundle", "run", "zach-demo_job", "-t", self.target]
        result = self.run_command(command, "ML Training Job", step_name)
        
        if result:
            self._mark_completed(step_name)
        
        return result
    
    def step4_deploy_app(self) -> bool:
        """Step 4: Sync files and deploy Databricks App."""
        step_name = "app_deploy"
        
        # Check if already completed
        if self.skip_completed and self._is_completed(step_name):
            print(f"\n{'='*70}")
            print("📱 STEP 4: DEPLOY DATABRICKS APP")
            print(f"{'='*70}")
            print("✅ App already deployed successfully - SKIPPING")
            last_run = self.state.get("last_updated", {}).get(step_name, "unknown")
            print(f"   Last successful run: {last_run}\n")
            return True
        
        print(f"\n{'='*70}")
        print("📱 STEP 4: DEPLOY DATABRICKS APP")
        print(f"{'='*70}")
        print("Syncing source files and deploying to Databricks Apps\n")
        
        # App configuration
        app_name = "zach-demo-app"
        workspace_path = "/Workspace/Users/zach.jacobson@databricks.com/zach-demo-app"
        source_dir = SCRIPT_DIR  # The src directory contains the app source code
        
        # Step 4a: Sync source files to Databricks workspace
        print(f"{'─'*70}")
        print("📁 Step 4a: Syncing source files to workspace")
        print(f"{'─'*70}")
        print(f"Source: {source_dir}")
        print(f"Destination: {workspace_path}\n")
        
        sync_command = [DATABRICKS_CLI, "sync", ".", workspace_path]
        sync_result = self.run_command(sync_command, "Sync Source Files", "app_sync")
        
        if not sync_result:
            print("❌ File sync failed - skipping app deploy")
            return False
        
        time.sleep(2)  # Brief pause between sync and deploy
        
        # Step 4b: Deploy the app
        print(f"\n{'─'*70}")
        print("🚀 Step 4b: Deploying to Databricks Apps")
        print(f"{'─'*70}")
        print(f"App name: {app_name}")
        print(f"Source path: {workspace_path}\n")
        
        deploy_command = [DATABRICKS_CLI, "apps", "deploy", app_name, "--source-code-path", workspace_path]
        deploy_result = self.run_command(deploy_command, "Deploy Databricks App", "app_deploy")
        
        if deploy_result:
            self._mark_completed(step_name)
            print(f"\n✅ App '{app_name}' deployed successfully!")
        
        return deploy_result
    
    def run_iteration(self) -> Dict[str, bool]:
        """
        Run one complete iteration of the deployment.
        
        Returns:
            Dictionary of step results {step_name: success}
        """
        self.current_iteration += 1
        
        print("\n" + "="*70)
        print(f"🔄 ITERATION {self.current_iteration} / {self.max_iterations}")
        print("="*70)
        print(f"Target: {self.target}")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        results = {}
        
        # Step 1: Bundle deploy
        results['bundle_deploy'] = self.step1_bundle_deploy()
        time.sleep(2)  # Brief pause between steps
        
        # Step 2: Setup scripts
        results['setup_scripts'] = self.step2_run_all_setup()
        time.sleep(2)
        
        # Step 3a: Pipeline
        results['pipeline'] = self.step3_run_pipeline()
        time.sleep(2)
        
        # Step 3b: SQL Job
        results['sql_job'] = self.step3_run_sql_job()
        time.sleep(2)
        
        # Step 3c: ML Job
        results['ml_job'] = self.step3_run_ml_job()
        time.sleep(2)
        
        # Step 4: Deploy App
        results['app_deploy'] = self.step4_deploy_app()
        
        return results
    
    def print_iteration_summary(self, results: Dict[str, bool]):
        """Print summary for current iteration."""
        print(f"\n{'='*70}")
        print(f"📊 ITERATION {self.current_iteration} SUMMARY")
        print(f"{'='*70}\n")
        
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        print(f"Results: {success_count}/{total_count} succeeded\n")
        
        for step, success in results.items():
            icon = "✅" if success else "❌"
            status = "SUCCESS" if success else "FAILED"
            ever = " (has succeeded before)" if self.ever_succeeded[step] and not success else ""
            print(f"  {icon} {step.replace('_', ' ').title()}: {status}{ever}")
        
        if success_count == total_count:
            print(f"\n🎉 All steps succeeded! Deployment converged.")
            return True
        else:
            print(f"\n⚠️  {total_count - success_count} step(s) still failing - will retry")
            return False
    
    def print_final_summary(self):
        """Print final deployment summary across all iterations."""
        print(f"\n\n{'='*70}")
        print("🎯 FINAL DEPLOYMENT SUMMARY")
        print(f"{'='*70}\n")
        
        print(f"Target: {self.target}")
        print(f"Total Iterations: {self.current_iteration}")
        print(f"Max Iterations: {self.max_iterations}\n")
        
        # Check if fully converged
        if self.current_iteration > 0:
            last_results = self.iteration_results[-1]['results']
            all_succeeded = all(last_results.values())
            
            if all_succeeded:
                print("✅ DEPLOYMENT SUCCESSFUL - Full Convergence Achieved!")
                print("\nAll components are deployed and operational:")
                for step in last_results.keys():
                    print(f"  ✅ {step.replace('_', ' ').title()}")
            else:
                print("❌ DEPLOYMENT INCOMPLETE - Did not fully converge")
                print(f"\nFailed to converge after {self.current_iteration} iterations")
                print("\nFailing components:")
                for step, success in last_results.items():
                    if not success:
                        print(f"  ❌ {step.replace('_', ' ').title()}")
                
                print("\nSuccessful components:")
                for step, success in last_results.items():
                    if success:
                        print(f"  ✅ {step.replace('_', ' ').title()}")
        
        # Show iteration progression
        if len(self.iteration_results) > 1:
            print(f"\n{'─'*70}")
            print("📈 CONVERGENCE PROGRESSION")
            print(f"{'─'*70}\n")
            
            for i, iter_data in enumerate(self.iteration_results, 1):
                results = iter_data['results']
                success_count = sum(1 for v in results.values() if v)
                total = len(results)
                percentage = (success_count / total * 100) if total > 0 else 0
                
                bar_length = 40
                filled = int(bar_length * success_count / total)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                print(f"Iteration {i}: [{bar}] {success_count}/{total} ({percentage:.0f}%)")
        
        # Show which components had issues
        print(f"\n{'─'*70}")
        print("🔍 COMPONENT HISTORY")
        print(f"{'─'*70}\n")
        
        all_steps = set()
        for iter_data in self.iteration_results:
            all_steps.update(iter_data['results'].keys())
        
        for step in sorted(all_steps):
            iterations_succeeded = []
            iterations_failed = []
            
            for i, iter_data in enumerate(self.iteration_results, 1):
                if step in iter_data['results']:
                    if iter_data['results'][step]:
                        iterations_succeeded.append(i)
                    else:
                        iterations_failed.append(i)
            
            total_attempts = len(iterations_succeeded) + len(iterations_failed)
            success_rate = len(iterations_succeeded) / total_attempts * 100 if total_attempts > 0 else 0
            
            status_icon = "✅" if iterations_succeeded and not iterations_failed else "⚠️" if iterations_succeeded else "❌"
            
            print(f"{status_icon} {step.replace('_', ' ').title()}")
            print(f"   Success rate: {success_rate:.0f}% ({len(iterations_succeeded)}/{total_attempts})")
            
            if iterations_failed:
                print(f"   Failed in iterations: {iterations_failed}")
            if iterations_succeeded:
                print(f"   Succeeded in iterations: {iterations_succeeded}")
            print()
    
    def deploy(self) -> int:
        """
        Execute convergence-based deployment.
        
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        print("""
╔══════════════════════════════════════════════════════════════════╗
║           Convergence-Based Deployment Orchestrator              ║
║                                                                  ║
║  Iteratively deploys resources until full convergence           ║
╚══════════════════════════════════════════════════════════════════╝
        """)
        
        print(f"Configuration:")
        print(f"  Target: {self.target}")
        print(f"  Max Iterations: {self.max_iterations}")
        print(f"  Skip Completed: {self.skip_completed}")
        print(f"  Strategy: Convergence (iterate until all succeed)")
        
        # Show state info
        completed_count = len([k for k, v in self.state.get("completed", {}).items() if v])
        if completed_count > 0 and self.skip_completed:
            print(f"  State: {completed_count} step(s) previously completed (will skip)")
        elif completed_count > 0:
            print(f"  State: {completed_count} step(s) previously completed (will rerun)")
        print()
        
        converged = False
        
        for iteration in range(1, self.max_iterations + 1):
            # Run one iteration
            results = self.run_iteration()
            
            # Store results
            self.iteration_results.append({
                'iteration': iteration,
                'results': results,
                'timestamp': time.time()
            })
            
            # Print iteration summary
            converged = self.print_iteration_summary(results)
            
            if converged:
                print(f"\n✨ Converged successfully in {iteration} iteration(s)!")
                break
            
            if iteration < self.max_iterations:
                print(f"\n⏳ Waiting 5 seconds before next iteration...\n")
                time.sleep(5)
        
        # Print final summary
        self.print_final_summary()
        
        # Determine exit code
        if converged:
            return 0
        else:
            print(f"\n⚠️  Did not converge within {self.max_iterations} iterations")
            print("Consider:")
            print("  1. Check logs for specific errors")
            print("  2. Verify permissions and configurations")
            print("  3. Run with --verbose for detailed output")
            print("  4. Increase --max-iterations if needed")
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convergence-based deployment orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy with default settings (max 10 iterations, skip completed)
  python deploy_all.py --target dev
  
  # Deploy with more iterations
  python deploy_all.py --target dev --max-iterations 15
  
  # Rerun everything (don't skip completed steps)
  python deploy_all.py --target dev --no-skip-completed
  
  # Reset state and start fresh
  python deploy_all.py --target dev --reset-state
  
  # Deploy to production
  python deploy_all.py --target prod
  
  # Verbose output for debugging
  python deploy_all.py --target dev --verbose

How it works:
  1. Deploys bundle (databricks bundle deploy)
     - Includes model serving endpoints (runs asynchronously, ~10 min)
  2. Runs setup scripts (databricks bundle run run_all_setup)
  3. Runs pipeline and jobs:
     a. DLT Pipeline (databricks bundle run zach-demo_pipeline)
     b. SQL Job - Create Metric View (databricks bundle run run_sql)
     c. ML Job - Model Training (databricks bundle run zach-demo_job)
  4. Deploys Databricks App:
     a. Syncs source files (databricks sync . /Workspace/Users/...)
     b. Deploys app (databricks apps deploy zach-demo-app --source-code-path ...)
  5. Repeats steps 1-4 until everything succeeds or max iterations reached
  
Smart features:
  - Skips jobs/pipelines that have already completed successfully
  - Tracks state across runs in .deployment_state.json
  - Long-running deployments (serving endpoints) run asynchronously
  - Bundle deploy continues while serving endpoint provisions
        """
    )
    
    parser.add_argument(
        "-t", "--target",
        default="dev",
        choices=["dev", "prod"],
        help="Deployment target (default: dev)"
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations before giving up (default: 10)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed command output"
    )
    
    parser.add_argument(
        "--no-skip-completed",
        action="store_true",
        help="Rerun all steps even if previously completed"
    )
    
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Reset deployment state (clear completed status)"
    )
    
    args = parser.parse_args()
    
    # Create orchestrator and run deployment
    orchestrator = ConvergenceDeployment(
        target=args.target,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
        skip_completed=not args.no_skip_completed,
        reset_state=args.reset_state
    )
    
    exit_code = orchestrator.deploy()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
