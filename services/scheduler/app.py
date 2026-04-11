from flask import Flask, jsonify
from flask_cors import CORS
import datetime
import requests
import schedule
import time
import threading
import logging
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
VISUALIZATION_SERVICE_URL = os.getenv('VISUALIZATION_SERVICE_URL', 'http://visualization-service:8002')
LOAD_SERVICE_URL = os.getenv('LOAD_SERVICE_URL', 'http://load-service:8003')

# Job status tracking
job_status = {
    "last_run": None,
    "next_run": None,
    "status": "initialized",
    "runs_count": 0,
    "errors": []
}

def trigger_data_update():
    """Function to trigger data updates in the pipeline"""
    try:
        logger.info("Starting scheduled data update...")
        job_status["status"] = "running"
        
        services_triggered = 0
        
        # 1. LOAD SERVICE - Trigger data loading to warehouse
        try:
            logger.info("Triggering Load Service...")
            response = requests.post(f"{LOAD_SERVICE_URL}/load/batch", 
                                   json={"tickers": "AAPL,GOOGL,MSFT", "period": "1mo"},
                                   timeout=30)
            
            if response.status_code in [200, 201]:
                logger.info("Successfully triggered Load Service")
                services_triggered += 1
            else:
                logger.warning(f"Load service returned status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Load service connection error: {str(e)}")

        # 2. VISUALIZATION SERVICE - Trigger dashboard refresh
        try:
            logger.info("Triggering Visualization Service...")
            response = requests.get(f"{VISUALIZATION_SERVICE_URL}/refresh", timeout=10)
            
            if response.status_code == 200:
                logger.info("Successfully triggered Visualization Service")
                services_triggered += 1
            else:
                logger.warning(f"Visualization service returned status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Visualization service connection error: {str(e)}")
        
        # Update job status
        job_status["last_run"] = datetime.datetime.utcnow().isoformat()
        job_status["runs_count"] += 1
        
        if services_triggered >= 2:  # Both services successful
            job_status["status"] = "completed"
            logger.info(f"Scheduled update completed - triggered {services_triggered}/2 services")
        elif services_triggered > 0:
            job_status["status"] = "partial"
            logger.warning(f"Partial update - triggered {services_triggered}/2 services")
        else:
            job_status["status"] = "error"
            logger.error("No services could be triggered")
        
    except Exception as e:
        logger.error(f"Error in scheduled data update: {str(e)}")
        job_status["status"] = "error"
        job_status["errors"].append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "error": str(e)
        })
        # Keep only last 10 errors
        if len(job_status["errors"]) > 10:
            job_status["errors"] = job_status["errors"][-10:]

def trigger_specific_service(service_name):
    """Trigger a specific service manually"""
    try:
        if service_name == "load":
            response = requests.post(f"{LOAD_SERVICE_URL}/load/batch", 
                                   json={"tickers": "AAPL,GOOGL,MSFT", "period": "1mo"}, timeout=30)
            return response.status_code in [200, 201]
            
        elif service_name == "visualization":
            response = requests.get(f"{VISUALIZATION_SERVICE_URL}/refresh", timeout=10)
            return response.status_code == 200
            
        return False
        
    except Exception as e:
        logger.error(f"Error triggering {service_name}: {str(e)}")
        return False

def run_scheduler():
    """Run the scheduler in a separate thread"""
    logger.info("Starting scheduler thread...")
    
    # Schedule the job to run every 30 seconds
    schedule.every(30).seconds.do(trigger_data_update)
    
    # Run initial update after 10 seconds (to allow services to start up)
    schedule.every().minute.at(":10").do(trigger_data_update).tag('initial')
    
    while True:
        try:
            # Update next run time
            jobs = schedule.get_jobs()
            if jobs:
                next_job = min(jobs, key=lambda job: job.next_run)
                job_status["next_run"] = next_job.next_run.isoformat()
            
            schedule.run_pending()
            time.sleep(1)
            
            # Remove the initial job after first run
            if job_status["runs_count"] >= 1:
                schedule.clear('initial')
                
        except Exception as e:
            logger.error(f"Error in scheduler thread: {str(e)}")
            time.sleep(5)  # Wait before retrying

@app.route("/health")
def health():
    """Comprehensive health check for scheduler service"""
    import time
    import psutil
    
    start_time = time.time()
    
    checks = {
        "service": "scheduler-service",
        "version": "1.0.0",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Test 1: System resource check
    try:
        memory_percent = psutil.virtual_memory().percent
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        if memory_percent > 90:
            checks["checks"]["memory"] = "unhealthy - high usage"
        elif memory_percent > 80:
            checks["checks"]["memory"] = "degraded - moderate usage"
        else:
            checks["checks"]["memory"] = "healthy"
        checks["memory_usage_percent"] = round(memory_percent, 1)
        
        if cpu_percent > 90:
            checks["checks"]["cpu"] = "unhealthy - high usage"
        elif cpu_percent > 80:
            checks["checks"]["cpu"] = "degraded - moderate usage"
        else:
            checks["checks"]["cpu"] = "healthy"
        checks["cpu_usage_percent"] = round(cpu_percent, 1)
        
    except Exception as e:
        checks["checks"]["system"] = f"degraded - {str(e)[:50]}"
    
    # Test 2: Scheduler status
    try:
        jobs_count = len(schedule.jobs)
        if jobs_count > 0:
            checks["checks"]["scheduler"] = "healthy"
            checks["active_jobs"] = jobs_count
        else:
            checks["checks"]["scheduler"] = "degraded - no scheduled jobs"
            checks["active_jobs"] = 0
            
    except Exception as e:
        checks["checks"]["scheduler"] = f"unhealthy - {str(e)[:50]}"
    
    # Test 3: Job execution history
    try:
        runs_count = job_status.get("runs_count", 0)
        last_run = job_status.get("last_run")
        current_status = job_status.get("status", "unknown")
        
        # Check if scheduler has been running
        if runs_count == 0:
            checks["checks"]["job_execution"] = "degraded - no runs yet"
        elif current_status == "error":
            checks["checks"]["job_execution"] = "unhealthy - last job failed"
        elif current_status in ["running", "completed", "partial"]:
            checks["checks"]["job_execution"] = "healthy"
        else:
            checks["checks"]["job_execution"] = f"degraded - status: {current_status}"
            
        checks["total_runs"] = runs_count
        checks["last_run"] = last_run
        
    except Exception as e:
        checks["checks"]["job_execution"] = f"degraded - {str(e)[:50]}"
    
    # Test 4: Service connectivity checks
    services_health = {
        "load_service": "unknown",
        "visualization_service": "unknown"
    }
    
    # Test Load Service
    try:
        response = requests.get(f"{LOAD_SERVICE_URL}/health", timeout=2)
        if response.status_code == 200:
            services_health["load_service"] = "healthy"
        else:
            services_health["load_service"] = f"degraded - status {response.status_code}"
    except Exception as e:
        services_health["load_service"] = f"unhealthy - {str(e)[:30]}"
    
    # Test Visualization Service  
    try:
        response = requests.get(f"{VISUALIZATION_SERVICE_URL}/health", timeout=2)
        if response.status_code == 200:
            services_health["visualization_service"] = "healthy"
        else:
            services_health["visualization_service"] = f"degraded - status {response.status_code}"
    except Exception as e:
        services_health["visualization_service"] = f"unhealthy - {str(e)[:30]}"
    
    checks["checks"]["service_connectivity"] = services_health
    
    # Evaluate service connectivity health
    unhealthy_services = sum(1 for status in services_health.values() if "unhealthy" in status)
    degraded_services = sum(1 for status in services_health.values() if "degraded" in status)
    
    if unhealthy_services > 1:
        checks["checks"]["services_overall"] = "unhealthy - multiple services down"
    elif unhealthy_services > 0 or degraded_services > 1:
        checks["checks"]["services_overall"] = "degraded - some services struggling"  
    else:
        checks["checks"]["services_overall"] = "healthy"
    
    # Test 5: Response time check
    response_time = (time.time() - start_time) * 1000
    checks["response_time_ms"] = round(response_time, 2)
    
    if response_time > 3000:
        checks["checks"]["response_time"] = "unhealthy - too slow"
    elif response_time > 1500:
        checks["checks"]["response_time"] = "degraded - slow"
    else:
        checks["checks"]["response_time"] = "healthy"
    
    # Overall status calculation
    unhealthy_count = sum(1 for check in checks["checks"].values() 
                         if isinstance(check, str) and "unhealthy" in check)
    degraded_count = sum(1 for check in checks["checks"].values() 
                        if isinstance(check, str) and "degraded" in check)
    
    if unhealthy_count > 0:
        checks["status"] = "unhealthy"
    elif degraded_count > 0:
        checks["status"] = "degraded"
    else:
        checks["status"] = "healthy"
    
    # Include job status for backwards compatibility
    checks["job_status"] = job_status
    
    return jsonify(checks)

@app.route("/status")
def status():
    """Get detailed scheduler status"""
    return jsonify({
        "service": "scheduler-service",
        "job_status": job_status,
        "scheduled_jobs": len(schedule.jobs),
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

@app.route("/trigger")
def manual_trigger():
    """Manually trigger a data update"""
    try:
        # Run the update function in a separate thread to avoid blocking
        threading.Thread(target=trigger_data_update, daemon=True).start()
        return jsonify({
            "message": "Data update triggered manually",
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            "error": f"Failed to trigger update: {str(e)}",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }), 500

@app.route("/trigger/<service_name>")
def manual_trigger_service(service_name):
    """Manually trigger a specific service"""
    try:
        success = trigger_specific_service(service_name)
        if success:
            return jsonify({
                "message": f"Successfully triggered {service_name} service",
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "error": f"Failed to trigger {service_name} service",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            "error": f"Error triggering {service_name}: {str(e)}",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }), 500

@app.route("/")
def home():
    """Headless microservice base route"""
    return jsonify({
        "service": "scheduler",
        "description": "CloudETL background orchestration service",
        "status": "running",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "endpoints": ["/health", "/status", "/trigger", "/trigger/<service_name>"]
    })

# robust lock to prevent multi-starts under threading
scheduler_lock = threading.Lock()
scheduler_started = False

def init_scheduler():
    global scheduler_started
    with scheduler_lock:
        if not scheduler_started:
            logger.info("Initializing Scheduler Background Thread...")
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            scheduler_started = True

# Start immediately on module import (Gunicorn safe for 1 worker)
init_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004, debug=False)