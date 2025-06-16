from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import os
import tempfile
import threading
import time
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename

# Import your analyzer class
from kroger_analyzer import KrogerReviewAnalyzer

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
        
    def update_status(self, status, progress=None, error=None, result_file=None):
        self.status = status
        if progress is not None:
            self.progress = progress
        if error:
            self.error_message = error
        if result_file:
            self.result_file = result_file

def run_analysis(job_id, category, max_products, max_reviews):
    """Run the analysis in a background thread"""
    job = analysis_jobs[job_id]
    
    try:
        job.update_status('initializing', 5)
        
        # Initialize analyzer
        analyzer = KrogerReviewAnalyzer(use_selenium=True, headless=True)
        
        job.update_status('searching', 15)
        
        # Run analysis
        analysis = analyzer.analyze_category_by_products(
            category=category,
            max_products=max_products,
            max_reviews_per_product=max_reviews
        )
        
        if not analysis:
            job.update_status('error', error="No products found for this category")
            return
            
        job.update_status('analyzing', 70)
        
        # Create temporary file for Excel output
        temp_dir = tempfile.mkdtemp()
        filename = f"{category.replace(' ', '_')}_analysis_{job_id[:8]}.xlsx"
        filepath = os.path.join(temp_dir, filename)
        
        # Export to Excel
        job.update_status('exporting', 85)
        analyzer.export_products_to_spreadsheet(analysis, filepath)
        
        job.update_status('completed', 100, result_file=filepath)
        
        # Clean up
        del analyzer
        
    except Exception as e:
        job.update_status('error', error=str(e))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        category = request.form.get('category', '').strip()
        max_products = int(request.form.get('max_products', 5))
        max_reviews = int(request.form.get('max_reviews', 10))
        
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
        
        # Start analysis in background thread
        thread = threading.Thread(target=run_analysis, args=(job_id, category, max_products, max_reviews))
        thread.daemon = True
        thread.start()
        
        return render_template('progress.html', job_id=job_id, category=category)
        
    except ValueError:
        flash('Please enter valid numbers for max products and max reviews', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error starting analysis: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/status/<job_id>')
def get_status(job_id):
    """API endpoint to check job status"""
    job = analysis_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'status': job.status,
        'progress': job.progress,
        'error': job.error_message,
        'category': job.category,
        'has_result': job.result_file is not None
    })

@app.route('/download/<job_id>')
def download_result(job_id):
    """Download the analysis result"""
    job = analysis_jobs.get(job_id)
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('index'))
    
    if job.status != 'completed' or not job.result_file:
        flash('Analysis not completed or file not available', 'error')
        return redirect(url_for('index'))
    
    if not os.path.exists(job.result_file):
        flash('Result file not found', 'error')
        return redirect(url_for('index'))
    
    filename = f"{job.category.replace(' ', '_')}_analysis.xlsx"
    
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
    
    return f"Cleaned up {len(jobs_to_remove)} old jobs"

if __name__ == '__main__':
    # For development
    app.run(debug=True, host='0.0.0.0', port=5000)
