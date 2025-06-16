from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import os
import tempfile
import threading
import time
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
import traceback
import logging

# Import your analyzer class
from kroger_analyzer import KrogerReviewAnalyzer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Store for tracking analysis jobs
analysis_jobs = {}

class AnalysisJob:
    def __init__(self, job_id, category, max_products, max_reviews):
        self.job_id = job_id
        self.category = category
        self.max_products = max_products
        self.max_reviews = max_reviews
        self.status = 'starting'
        self.progress = 0
        self.result_file = None
        self.error_message = None
        self.created_at = datetime.now()
        logger.info(f"Created job {job_id} for category '{category}'")
        
    def update_status(self, status, progress=None, error=None, result_file=None):
        logger.info(f"Job {self.job_id}: {status} (progress: {progress}%)")
        self.status = status
        if progress is not None:
            self.progress = progress
        if error:
            self.error_message = error
            logger.error(f"Job {self.job_id} error: {error}")
        if result_file:
            self.result_file = result_file

def run_analysis(job_id, category, max_products, max_reviews):
    """Run the analysis in a background thread"""
    logger.info(f"Starting analysis thread for job {job_id}")
    job = analysis_jobs.get(job_id)
    
    if not job:
        logger.error(f"Job {job_id} not found in analysis_jobs")
        return
    
    try:
        job.update_status('initializing', 5)
        
        # Initialize analyzer
        logger.info(f"Initializing analyzer for job {job_id}")
        analyzer = KrogerReviewAnalyzer(use_selenium=True, headless=True)
        
        job.update_status('searching', 15)
        logger.info(f"Starting product search for '{category}'")
        
        # Run analysis
        analysis = analyzer.analyze_category_by_products(
            category=category,
            max_products=max_products,
            max_reviews_per_product=max_reviews
        )
        
        logger.info(f"Analysis completed for job {job_id}. Result: {analysis is not None}")
        
        if not analysis:
            job.update_status('error', error="No products found for this category")
            return
            
        job.update_status('analyzing', 70)
        
        # Create temporary file for Excel output
        temp_dir = tempfile.mkdtemp()
        filename = f"{category.replace(' ', '_')}_analysis_{job_id[:8]}.xlsx"
        filepath = os.path.join(temp_dir, filename)
        
        logger.info(f"Exporting to Excel: {filepath}")
        
        # Export to Excel
        job.update_status('exporting', 85)
        result_file = analyzer.export_products_to_spreadsheet(analysis, filepath)
        
        if result_file and os.path.exists(result_file):
            job.update_status('completed', 100, result_file=result_file)
            logger.info(f"Job {job_id} completed successfully. File: {result_file}")
        else:
            job.update_status('error', error="Failed to create Excel file")
        
        # Clean up
        del analyzer
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.error(f"Job {job_id} failed with exception: {error_msg}")
        logger.error(traceback.format_exc())
        job.update_status('error', error=error_msg)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        category = request.form.get('category', '').strip()
        max_products = int(request.form.get('max_products', 5))
        max_reviews = int(request.form.get('max_reviews', 10))
        
        logger.info(f"New analysis request: category='{category}', max_products={max_products}, max_reviews={max_reviews}")
        
        # Validation
        if not category:
            flash('Please enter a search category', 'error')
            return redirect(url_for('index'))
            
        if max_products < 1 or max_products > 20:
            flash('Max products must be between 1 and 20', 'error')
            return redirect(url_for('index'))
            
        if max_reviews < 1 or max_reviews > 50:
            flash('Max reviews must be between 1 and 50', 'error')
            return redirect(url_for('index'))
        
        # Create new job
        job_id = str(uuid.uuid4())
        job = AnalysisJob(job_id, category, max_products, max_reviews)
        analysis_jobs[job_id] = job
        
        logger.info(f"Created job {job_id}, starting background thread")
        
        # Start analysis in background thread
        thread = threading.Thread(target=run_analysis, args=(job_id, category, max_products, max_reviews))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Background thread started for job {job_id}")
        
        return render_template('progress.html', job_id=job_id, category=category)
        
    except ValueError as e:
        logger.error(f"ValueError in analyze: {e}")
        flash('Please enter valid numbers for max products and max reviews', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Exception in analyze: {e}")
        logger.error(traceback.format_exc())
        flash(f'Error starting analysis: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/status/<job_id>')
def get_status(job_id):
    """API endpoint to check job status"""
    logger.info(f"Status check for job {job_id}")
    job = analysis_jobs.get(job_id)
    if not job:
        logger.warning(f"Job {job_id} not found in analysis_jobs. Available jobs: {list(analysis_jobs.keys())}")
        return jsonify({'error': 'Job not found'}), 404
    
    response_data = {
        'status': job.status,
        'progress': job.progress,
        'error': job.error_message,
        'category': job.category,
        'has_result': job.result_file is not None
    }
    
    logger.info(f"Job {job_id} status: {response_data}")
    return jsonify(response_data)

@app.route('/download/<job_id>')
def download_result(job_id):
    """Download the analysis result"""
    logger.info(f"Download request for job {job_id}")
    job = analysis_jobs.get(job_id)
    if not job:
        logger.warning(f"Download failed: Job {job_id} not found")
        flash('Job not found', 'error')
        return redirect(url_for('index'))
    
    if job.status != 'completed' or not job.result_file:
        logger.warning(f"Download failed: Job {job_id} not completed or no file. Status: {job.status}, File: {job.result_file}")
        flash('Analysis not completed or file not available', 'error')
        return redirect(url_for('index'))
    
    if not os.path.exists(job.result_file):
        logger.warning(f"Download failed: File {job.result_file} does not exist")
        flash('Result file not found', 'error')
        return redirect(url_for('index'))
    
    filename = f"{job.category.replace(' ', '_')}_analysis.xlsx"
    logger.info(f"Sending file {job.result_file} as {filename}")
    
    return send_file(
        job.result_file,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/cleanup')
def cleanup_old_jobs():
    """Clean up old jobs (call this periodically)"""
    current_time = datetime.now()
    jobs_to_remove = []
    
    for job_id, job in analysis_jobs.items():
        # Remove jobs older than 1 hour
        if (current_time - job.created_at).total_seconds() > 3600:
            # Clean up file if it exists
            if job.result_file and os.path.exists(job.result_file):
                try:
                    os.remove(job.result_file)
                    # Try to remove the temp directory too
                    temp_dir = os.path.dirname(job.result_file)
                    if os.path.exists(temp_dir):
                        os.rmdir(temp_dir)
                except:
                    pass
            jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del analysis_jobs[job_id]
    
    logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
    return f"Cleaned up {len(jobs_to_remove)} old jobs"

@app.route('/debug/jobs')
def debug_jobs():
    """Debug endpoint to see all jobs"""
    jobs_info = {}
    for job_id, job in analysis_jobs.items():
        jobs_info[job_id] = {
            'category': job.category,
            'status': job.status,
            'progress': job.progress,
            'error': job.error_message,
            'created_at': job.created_at.isoformat(),
            'has_file': job.result_file is not None
        }
    return jsonify(jobs_info)

if __name__ == '__main__':
    # For development
    app.run(debug=True, host='0.0.0.0', port=5000)