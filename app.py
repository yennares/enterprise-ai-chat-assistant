# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv
import json
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hr_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(50), nullable=False)
    position = db.Column(db.String(80), nullable=False)
    join_date = db.Column(db.Date, nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)

class LeaveBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sick_leave_balance = db.Column(db.Integer, default=12)
    vacation_leave_balance = db.Column(db.Integer, default=21)
    personal_leave_balance = db.Column(db.Integer, default=5)
    year = db.Column(db.Integer, nullable=False)
    
class Documents(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    passport_expiry_date = db.Column(db.Date, nullable=True)
    visa_expiry_date = db.Column(db.Date, nullable=True)
    id_card_expiry_date = db.Column(db.Date, nullable=True)

class SalaryInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    basic_salary = db.Column(db.Float, nullable=False)
    allowances = db.Column(db.Float, default=0)
    bonus = db.Column(db.Float, default=0)
    effective_date = db.Column(db.Date, nullable=False)

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['full_name'] = user.full_name
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    leave_balance = LeaveBalance.query.filter_by(user_id=user.id, year=datetime.now().year).first()
    documents = Documents.query.filter_by(user_id=user.id).first()
    salary = SalaryInfo.query.filter_by(user_id=user.id).order_by(SalaryInfo.effective_date.desc()).first()
    
    return render_template('dashboard.html', user=user, leave_balance=leave_balance, 
                         documents=documents, salary=salary)

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat_api():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_message = request.json.get('message', '')
    user_id = session['user_id']
    username = session['username']
    full_name = session['full_name']

    try:
        # Step 1: Parse user intent using OpenAI
        intent_response = client.chat.completions.create(
            model="gpt-4o-mini", #gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": """You are an HR assistant that extracts intent from user queries.
                Respond only in JSON format with 'intent' and 'parameters' fields.
                Respond to user respectfully if they enquire anything in general apart from the below intents.
                You may mention that this is Corporate Portal and need to enquire only about company and personal information.

                Possible intents:
                - leave_balance: when user asks about remaining leaves
                - passport_expiry: when user asks about passport expiration
                - visa_expiry: when user asks about visa expiration
                - id_card_expiry: when user asks about ID card expiration
                - salary_info: when user asks about salary details
                - document_expiry: when user asks about any document expiration
                - user_info: when user asks about their department, position, joining date, employee ID, tenure, how long they've been working, or other personal employment details
                - general_info: for other HR related queries. Anything apart from this, please navigate them back to corporate.
                - other_employee_info: when the user is asking about other user's information.

                Example response: {"intent": "leave_balance", "parameters": {"leave_type": "sick"}}"""},
                {"role": "user", "content": f"user_message is: {user_message} and my username is: {username} and my employee id is: {user_id}"}
            ],
            temperature=0.1
        )

        intent_data = json.loads(intent_response.choices[0].message.content)
        intent = intent_data.get('intent')
        parameters = intent_data.get('parameters', {})

        # Step 2: Query database based on intent
        query_result = execute_hr_query(intent, parameters, user_id)

        # Step 3: Generate natural language response
        response = generate_response(user_message, query_result, intent, parameters)

        return jsonify({'response': response})

    except Exception as e:
        print(f"Chat API Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return jsonify({'response': f'Sorry, I encountered an error: {str(e)}. Please try again.'})

def execute_hr_query(intent, parameters, user_id):
    """Execute database queries based on parsed intent"""
    try:
        if intent == 'leave_balance':
            leave_balance = LeaveBalance.query.filter_by(user_id=user_id, year=datetime.now().year).first()
            if not leave_balance:
                return None
                
            leave_type = parameters.get('leave_type', '').lower()
            if 'sick' in leave_type:
                return {'type': 'sick_leave', 'balance': leave_balance.sick_leave_balance}
            elif 'vacation' in leave_type or 'annual' in leave_type:
                return {'type': 'vacation_leave', 'balance': leave_balance.vacation_leave_balance}
            elif 'personal' in leave_type:
                return {'type': 'personal_leave', 'balance': leave_balance.personal_leave_balance}
            else:
                return {
                    'type': 'all_leaves',
                    'sick': leave_balance.sick_leave_balance,
                    'vacation': leave_balance.vacation_leave_balance,
                    'personal': leave_balance.personal_leave_balance
                }
        
        elif intent == 'passport_expiry':
            documents = Documents.query.filter_by(user_id=user_id).first()
            if not documents or not documents.passport_expiry_date:
                return None

            days_until_expiry = (documents.passport_expiry_date - datetime.now().date()).days
            return {
                'passport': {
                    'expiry_date': documents.passport_expiry_date.strftime('%B %d, %Y'),
                    'days_until_expiry': days_until_expiry
                }
            }

        elif intent == 'visa_expiry':
            documents = Documents.query.filter_by(user_id=user_id).first()
            if not documents or not documents.visa_expiry_date:
                return None

            days_until_expiry = (documents.visa_expiry_date - datetime.now().date()).days
            return {
                'visa': {
                    'expiry_date': documents.visa_expiry_date.strftime('%B %d, %Y'),
                    'days_until_expiry': days_until_expiry
                }
            }

        elif intent == 'id_card_expiry':
            documents = Documents.query.filter_by(user_id=user_id).first()
            if not documents or not documents.id_card_expiry_date:
                return None

            days_until_expiry = (documents.id_card_expiry_date - datetime.now().date()).days
            return {
                'id_card': {
                    'expiry_date': documents.id_card_expiry_date.strftime('%B %d, %Y'),
                    'days_until_expiry': days_until_expiry
                }
            }

        elif intent == 'document_expiry':
            documents = Documents.query.filter_by(user_id=user_id).first()
            if not documents:
                return None

            result = {}
            if documents.passport_expiry_date:
                days_until_expiry = (documents.passport_expiry_date - datetime.now().date()).days
                result['passport'] = {
                    'expiry_date': documents.passport_expiry_date.strftime('%B %d, %Y'),
                    'days_until_expiry': days_until_expiry
                }

            if documents.visa_expiry_date:
                days_until_expiry = (documents.visa_expiry_date - datetime.now().date()).days
                result['visa'] = {
                    'expiry_date': documents.visa_expiry_date.strftime('%B %d, %Y'),
                    'days_until_expiry': days_until_expiry
                }

            if documents.id_card_expiry_date:
                days_until_expiry = (documents.id_card_expiry_date - datetime.now().date()).days
                result['id_card'] = {
                    'expiry_date': documents.id_card_expiry_date.strftime('%B %d, %Y'),
                    'days_until_expiry': days_until_expiry
                }

            return result if result else None
        

        elif intent == 'user_info':
            user = User.query.filter_by(id=user_id).first()
            if not user:
                return None

            # Calculate tenure
            tenure_days = (datetime.now().date() - user.join_date).days
            tenure_years = tenure_days // 365
            tenure_months = (tenure_days % 365) // 30

            return {
                'full_name': user.full_name,
                'employee_id': user.employee_id,
                'department': user.department,
                'position': user.position,
                'join_date': user.join_date.strftime('%B %d, %Y'),
                'email': user.email,
                'tenure_years': tenure_years,
                'tenure_months': tenure_months,
                'tenure_days': tenure_days
            }

        elif intent == 'other_employee_info':
            return "It is unethical to enquiry about other user information. Becareful, this might be report to your Manager."


        elif intent == 'salary_info':
            salary = SalaryInfo.query.filter_by(user_id=user_id).order_by(SalaryInfo.effective_date.desc()).first()
            if not salary:
                return None
            
            total_salary = salary.basic_salary + salary.allowances + salary.bonus
            return {
                'basic_salary': salary.basic_salary,
                'allowances': salary.allowances,
                'bonus': salary.bonus,
                'total_salary': total_salary,
                'effective_date': salary.effective_date.strftime('%B %Y')
            }
        
        return None
    except Exception as e:
        return None

def generate_response(user_query, query_result, intent, parameters):
    """Generate natural language response using OpenAI"""
    try:
        if not query_result:
            return "I couldn't find the information you're looking for. Please contact HR for assistance."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful HR assistant. Generate a natural, friendly response based on the user's query and the data provided. Be conversational and professional."},
                {"role": "user", "content": f"User query: {user_query}\nData: {json.dumps(query_result)}\n\nGenerate a helpful response:"}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content
    except Exception as e:
        print(f"Response generation error: {str(e)}")
        return f"I'm having trouble generating a response right now: {str(e)}. Please try again."

def init_db():
    """Initialize database with sample data"""
    with app.app_context():
        db.create_all()
        
        # Check if users already exist
        if User.query.first():
            return
        
        # Create sample users
        user1 = User(
            username='emp1',
            password_hash=generate_password_hash('emp1'),
            full_name='John Smith',
            email='john.smith@company.com',
            department='Engineering',
            position='Senior Developer',
            join_date=datetime(2022, 1, 15).date(),
            employee_id='EMP001'
        )
        
        user2 = User(
            username='emp2',
            password_hash=generate_password_hash('emp2'),
            full_name='Sarah Johnson',
            email='sarah.johnson@company.com',
            department='Marketing',
            position='Marketing Manager',
            join_date=datetime(2021, 6, 1).date(),
            employee_id='EMP002'
        )
        
        db.session.add(user1)
        db.session.add(user2)
        db.session.commit()
        
        # Create leave balances
        leave1 = LeaveBalance(
            user_id=user1.id,
            sick_leave_balance=8,
            vacation_leave_balance=15,
            personal_leave_balance=3,
            year=2024
        )
        
        leave2 = LeaveBalance(
            user_id=user2.id,
            sick_leave_balance=10,
            vacation_leave_balance=18,
            personal_leave_balance=4,
            year=2024
        )
        
        db.session.add(leave1)
        db.session.add(leave2)
        
        # Create documents
        doc1 = Documents(
            user_id=user1.id,
            passport_expiry_date=datetime(2026, 8, 15).date(),
            visa_expiry_date=datetime(2025, 12, 30).date()
        )
        
        doc2 = Documents(
            user_id=user2.id,
            passport_expiry_date=datetime(2025, 3, 22).date(),
            visa_expiry_date=datetime(2025, 9, 15).date()
        )
        
        db.session.add(doc1)
        db.session.add(doc2)
        
        # Create salary info
        salary1 = SalaryInfo(
            user_id=user1.id,
            basic_salary=75000,
            allowances=5000,
            bonus=8000,
            effective_date=datetime(2024, 1, 1).date()
        )
        
        salary2 = SalaryInfo(
            user_id=user2.id,
            basic_salary=65000,
            allowances=4500,
            bonus=6500,
            effective_date=datetime(2024, 1, 1).date()
        )
        
        db.session.add(salary1)
        db.session.add(salary2)
        
        db.session.commit()
        print("Database initialized with sample data!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)