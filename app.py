from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import os
import tempfile
import threading
import time
import json
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
# Store for dashboard data (in production, use a database)
analysis_results = {}

class AnalysisJob:
    def __init__(self, job_id, category, max_products, max_reviews):
        self.job_id = job_id
        self.category = category
        self.max_products = max_products
        self.max_reviews = max_reviews
        self.status = 'starting'
        self.progress = 0
        self.result_file = None
        self.analysis_data = None
        self.error_message = None
        self.created_at = datetime.now()
        self.thread = None
        logger.info(f"Created job {job_id} for category '{category}'")
        
    def update_status(self, status, progress=None, error=None, result_file=None, analysis_data=None):
        logger.info(f"Job {self.job_id}: {status} (progress: {progress}%)")
        self.status = status
        if progress is not None:
            self.progress = progress
        if error:
            self.error_message = error
            logger.error(f"Job {self.job_id} error: {error}")
        if result_file:
            self.result_file = result_file
        if analysis_data:
            self.analysis_data = analysis_data

def run_analysis(job_id, category, max_products, max_reviews):
    """Run the analysis in a background thread with timeout tracking"""
    logger.info(f"Starting analysis thread for job {job_id}")
    job = analysis_jobs.get(job_id)
    
    if not job:
        logger.error(f"Job {job_id} not found in analysis_jobs")
        return
    
    start_time = time.time()
    max_duration = 900  # 15 minutes timeout
    
    try:
        job.update_status('initializing', 5)
        
        # Check timeout
        if time.time() - start_time > max_duration:
            job.update_status('error', error="Analysis timed out during initialization")
            return
        
        # Initialize analyzer with fallback strategy
        logger.info(f"Initializing analyzer for job {job_id}")
        
        try:
            analyzer = KrogerReviewAnalyzer(use_selenium=True, headless=True)
            logger.info("✅ Analyzer initialized with Selenium")
        except Exception as e:
            logger.warning(f"Selenium failed, using requests-only mode: {e}")
            analyzer = KrogerReviewAnalyzer(use_selenium=False, headless=True)
        
        # Check timeout
        if time.time() - start_time > max_duration:
            job.update_status('error', error="Analysis timed out during analyzer setup")
            return
        
        job.update_status('searching', 15)
        logger.info(f"Starting product search for '{category}'")
        
        # Run analysis with progress tracking
        try:
            analysis = analyzer.analyze_category_by_products(
                category=category,
                max_products=max_products,
                max_reviews_per_product=max_reviews
            )
            
            # Check timeout after analysis
            if time.time() - start_time > max_duration:
                job.update_status('error', error="Analysis timed out during execution")
                return
            
            logger.info(f"Analysis completed for job {job_id}. Result: {analysis is not None}")
            
            if not analysis:
                job.update_status('error', error="No products found for this category. This could be due to website restrictions or the category not existing.")
                return
            
        except Exception as e:
            logger.error(f"Analysis execution failed: {e}")
            job.update_status('error', error=f"Analysis failed: {str(e)}")
            return
            
        job.update_status('analyzing', 70)
        
        # Store analysis data for dashboard
        analysis_results[job_id] = analysis
        
        # Create temporary file for Excel output
        temp_dir = tempfile.mkdtemp()
        filename = f"{category.replace(' ', '_')}_analysis_{job_id[:8]}.xlsx"
        filepath = os.path.join(temp_dir, filename)
        
        logger.info(f"Exporting to Excel: {filepath}")
        
        # Export to Excel
        job.update_status('exporting', 85)
        try:
            result_file = analyzer.export_products_to_spreadsheet(analysis, filepath)
            
            if result_file and os.path.exists(result_file):
                job.update_status('completed', 100, result_file=result_file, analysis_data=analysis)
                logger.info(f"Job {job_id} completed successfully. File: {result_file}")
            else:
                job.update_status('completed', 100, analysis_data=analysis)
                logger.info(f"Job {job_id} completed (analysis only, Excel export failed)")
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            # Still mark as completed if we have analysis data
            job.update_status('completed', 100, analysis_data=analysis)
            logger.info(f"Job {job_id} completed (analysis only, Excel export failed)")
        
        # Clean up
        try:
            del analyzer
        except:
            pass
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        logger.error(f"Job {job_id} failed with exception: {error_msg}")
        logger.error(traceback.format_exc())
        job.update_status('error', error=error_msg)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Show the interactive dashboard"""
    return render_template('dashboard.html')

@app.route('/dashboard/<job_id>')
def dashboard_with_job(job_id):
    """Show dashboard for a specific analysis job"""
    job = analysis_jobs.get(job_id)
    if not job or job.status != 'completed':
        flash('Analysis not found or not completed', 'error')
        return redirect(url_for('index'))
    
    return render_template('dashboard.html', job_id=job_id)

@app.route('/api/dashboard-data')
def get_dashboard_data():
    """API endpoint to get all dashboard data"""
    try:
        all_reviews = []
        
        for job_id, analysis_data in analysis_results.items():
            if analysis_data and 'products' in analysis_data:
                for product in analysis_data['products']:
                    sample_reviews = product.get('sample_reviews', {})
                    
                    for sentiment_type in ['positive', 'negative', 'neutral']:
                        for review in sample_reviews.get(sentiment_type, []):
                            review_entry = {
                                'job_id': job_id,
                                'category': analysis_data.get('category', ''),
                                'product_name': product.get('product_name', ''),
                                'product_url': product.get('product_url', ''),
                                'rating': review.get('rating'),
                                'text': review.get('text', ''),
                                'author': review.get('author', ''),
                                'datetime': review.get('datetime'),
                                'sentiment_score': _calculate_sentiment_score(sentiment_type),
                                'sentiment_category': sentiment_type
                            }
                            
                            if not review_entry['datetime']:
                                review_entry['datetime'] = datetime.now().isoformat()
                            
                            all_reviews.append(review_entry)
        
        return jsonify(all_reviews)
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard-data/<job_id>')
def get_job_dashboard_data(job_id):
    """API endpoint to get dashboard data for a specific job"""
    try:
        analysis_data = analysis_results.get(job_id)
        if not analysis_data:
            return jsonify({'error': 'Analysis not found'}), 404
        
        reviews = []
        
        if 'products' in analysis_data:
            for product in analysis_data['products']:
                sample_reviews = product.get('sample_reviews', {})
                
                for sentiment_type in ['positive', 'negative', 'neutral']:
                    for review in sample_reviews.get(sentiment_type, []):
                        review_entry = {
                            'job_id': job_id,
                            'category': analysis_data.get('category', ''),
                            'product_name': product.get('product_name', ''),
                            'product_url': product.get('product_url', ''),
                            'rating': review.get('rating'),
                            'text': review.get('text', ''),
                            'author': review.get('author', ''),
                            'datetime': review.get('datetime'),
                            'sentiment_score': _calculate_sentiment_score(sentiment_type),
                            'sentiment_category': sentiment_type
                        }
                        
                        if not review_entry['datetime']:
                            review_entry['datetime'] = datetime.now().isoformat()
                        
                        reviews.append(review_entry)
        
        return jsonify(reviews)
        
    except Exception as e:
        logger.error(f"Error getting job dashboard data: {e}")
        return jsonify({'error': str(e)}), 500

def _calculate_sentiment_score(sentiment_type):
    """Convert sentiment category to approximate score"""
    if sentiment_type == 'positive':
        return 0.5
    elif sentiment_type == 'negative':
        return -0.5
    else:
        return 0.0

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
        
        # Limit resources for cloud deployment
        if max_products > 10:
            max_products = 10
            flash('Max products limited to 10 for cloud deployment', 'warning')
            
        if max_reviews > 20:
            max_reviews = 20
            flash('Max reviews limited to 20 for cloud deployment', 'warning')
        
        # Create new job
        job_id = str(uuid.uuid4())
        job = AnalysisJob(job_id, category, max_products, max_reviews)
        analysis_jobs[job_id] = job
        
        logger.info(f"Created job {job_id}, starting background thread")
        
        # Start analysis in background thread (without signal handling)
        thread = threading.Thread(target=run_analysis, args=(job_id, category, max_products, max_reviews))
        thread.daemon = True
        thread.start()
        job.thread = thread
        
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
    
    # Check if job has been running too long without progress
    time_running = (datetime.now() - job.created_at).total_seconds()
    if time_running > 900 and job.status in ['starting', 'initializing', 'searching']:  # 15 minutes
        logger.warning(f"Job {job_id} appears stuck, marking as error")
        job.update_status('error', error="Analysis timed out. The website may be blocking automated requests or there may be a technical issue.")
    
    response_data = {
        'status': job.status,
        'progress': job.progress,
        'error': job.error_message,
        'category': job.category,
        'has_result': job.result_file is not None,
        'has_dashboard_data': job.analysis_data is not None,
        'running_time': int(time_running)
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

@app.route('/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running job"""
    logger.info(f"Cancel request for job {job_id}")
    job = analysis_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.status in ['completed', 'error']:
        return jsonify({'message': 'Job already finished'})
    
    # Mark job as cancelled
    job.update_status('error', error="Job cancelled by user")
    logger.info(f"Job {job_id} cancelled by user")
    
    return jsonify({'message': 'Job cancelled successfully'})

@app.route('/cleanup')
def cleanup_old_jobs():
    """Clean up old jobs (call this periodically)"""
    current_time = datetime.now()
    jobs_to_remove = []
    
    for job_id, job in analysis_jobs.items():
        # Remove jobs older than 2 hours
        if (current_time - job.created_at).total_seconds() > 7200:
            # Clean up file if it exists
            if job.result_file and os.path.exists(job.result_file):
                try:
                    os.remove(job.result_file)
                    temp_dir = os.path.dirname(job.result_file)
                    if os.path.exists(temp_dir):
                        os.rmdir(temp_dir)
                except:
                    pass
            
            # Remove from analysis results too
            if job_id in analysis_results:
                del analysis_results[job_id]
                
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
        running_time = (datetime.now() - job.created_at).total_seconds()
        jobs_info[job_id] = {
            'category': job.category,
            'status': job.status,
            'progress': job.progress,
            'error': job.error_message,
            'created_at': job.created_at.isoformat(),
            'running_time_seconds': int(running_time),
            'has_file': job.result_file is not None,
            'has_analysis_data': job.analysis_data is not None
        }
    return jsonify(jobs_info)

@app.route('/debug/analysis-results')
def debug_analysis_results():
    """Debug endpoint to see stored analysis results"""
    results_info = {}
    for job_id, analysis_data in analysis_results.items():
        if analysis_data:
            results_info[job_id] = {
                'category': analysis_data.get('category', ''),
                'total_products': analysis_data.get('total_products_analyzed', 0),
                'has_summary': 'summary' in analysis_data,
                'product_count': len(analysis_data.get('products', []))
            }
        else:
            results_info[job_id] = {'error': 'No analysis data'}
    
    return jsonify(results_info)

@app.route('/test-analyzer')
def test_analyzer():
    """Test endpoint to verify analyzer functionality"""
    try:
        logger.info("Testing analyzer initialization...")
        
        # Test with requests-only mode first
        analyzer = KrogerReviewAnalyzer(use_selenium=False, headless=True)
        logger.info("✅ Requests-only analyzer initialized")
        
        # Test with Selenium
        try:
            selenium_analyzer = KrogerReviewAnalyzer(use_selenium=True, headless=True)
            logger.info("✅ Selenium analyzer initialized")
            selenium_working = True
        except Exception as e:
            logger.warning(f"❌ Selenium analyzer failed: {e}")
            selenium_working = False
        
        return jsonify({
            'requests_analyzer': 'working',
            'selenium_analyzer': 'working' if selenium_working else 'failed',
            'chrome_available': os.path.exists('/usr/bin/google-chrome'),
            'chromedriver_available': os.path.exists('/usr/local/bin/chromedriver'),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 10000))
    # For production deployment
    app.run(debug=False, host='0.0.0.0', port=port)