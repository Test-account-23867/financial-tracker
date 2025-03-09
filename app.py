from flask import request, render_template, redirect, url_for,flash
from flask_login import login_user, login_required, logout_user,current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import datetime
from __init__ import app, db, login_manager
from models import User, Category, Transaction


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            user = User.query.filter_by(email=email).first()
            if user and (check_password_hash(user.password, password)):
                login_user(user)
                return redirect(url_for('home'))
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
        except Exception as e:
            print(e)
            flash('unknown error', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            if User.query.filter_by(email=email).first():
                flash('User already exists','warning')
                return redirect(url_for('register'))
            password = generate_password_hash(request.form.get('password'))
            user = User(name = name, email = email, password = password)
            db.session.add(user)
            db.session.commit()
            flash('User created successfully','success')
            return redirect(url_for('login'))
        except Exception as e:
            print(e)
            flash('unknown error', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')



@app.route('/')
@login_required
def home():

    # # total_income = 
    # # total_expenses = Transaction.query.filter_by(type='expense').all()

    # Get financial summary data
    total_income = db.session.query(func.sum(Transaction.amount)) \
        .filter(Transaction.user_id == current_user.id, Transaction.type == 'income').scalar() or 0
    
    #scalar returns a single value/None, here it returns the sum, if category income/expense
    
    total_expenses = db.session.query(func.sum(Transaction.amount)) \
        .filter(Transaction.user_id == current_user.id, Transaction.type == 'expense').scalar() or 0
    
    balance = total_income - total_expenses

    # Get expense categories with totals for the chart
    expense_categories = db.session.query(
        Category.name, 
        func.sum(Transaction.amount).label('total')
    ).join(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == 'expense',
        Category.id == Transaction.category_id
    ).group_by(Category.name).all()

    # for chart
    expense_categories = [{'name': cat.name, 'total': float(cat.total)} for cat in expense_categories]

    # Get recent transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id) \
        .order_by(Transaction.date.desc()).limit(10).all()

    return render_template('home.html',
                           total_income=total_income,
                           total_expenses=total_expenses,
                           balance=balance,
                           expense_categories=expense_categories,
                           recent_transactions=recent_transactions)


@app.route('/transactions')
@login_required
def transactions():
    
    # Initialize the base query first
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    transaction_type = request.args.get('type')
    category_id = request.args.get('category_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    if transaction_type:
        query = query.filter_by(type=transaction_type)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if date_from:
        date_from = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(Transaction.date >= date_from)
    if date_to:
        date_to = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(Transaction.date <= date_to)

    transactions = query.order_by(Transaction.date.desc()).all()
    # Get categories for the filter dropdown
    categories = Category.query.filter_by(user_id=current_user.id).all()

    return render_template('transactions.html', transactions=transactions, categories=categories)


@app.route('/add-transaction', methods=['GET','POST'])
@login_required
def add_transaction():
    if request.method == 'POST':
        try:
            transaction_type = request.form.get('type')
            amount = request.form.get('amount')
            description = request.form.get('description')
            date_str = request.form.get('date')
            category_id = request.form.get('category_id') or None

            transaction_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

            transaction = Transaction(
                type = transaction_type,
                amount = amount,
                description = description,
                date = transaction_date,
                category_id = category_id,
                user_id = current_user.id
            )

            db.session.add(transaction)
            db.session.commit()

            flash('Transaction added successfully', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            print(e)
            flash('An error occured while adding the transaction', 'error')

    categories = Category.query.filter_by(user_id=current_user.id).all()
    today = datetime.datetime.today().strftime('%Y-%m-%d')

    return render_template('add_transaction.html', categories=categories,today=today)


@app.route('/edit-transaction/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(id):
    transaction = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            transaction.type = request.form.get('type')
            transaction.amount = float(request.form.get('amount'))
            transaction.description = request.form.get('description')
            transaction.date = datetime.datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            transaction.category_id = request.form.get('category_id') or None
            
            db.session.commit()
            flash('Transaction updated successfully', 'success')
            return redirect(url_for('transactions'))
        except Exception as e:
            db.session.rollback()
            print(e)
            flash('An error occurred while updating the transaction', 'error')
    
    # Get all categories for the user
    categories = Category.query.filter_by(user_id=current_user.id).all()
    
    return render_template('add_transaction.html', transaction=transaction, categories=categories)


@app.route('/delete-transaction/<int:id>')
@login_required
def delete_transaction(id):
    transaction = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(e)
        flash('An error occurred while deleting the transaction', 'error')
    
    return redirect(url_for('transactions'))


@app.route('/categories')
@login_required
def categories():
    income_categories = Category.query.filter_by(user_id=current_user.id, type='income').all()
    expense_categories = Category.query.filter_by(user_id=current_user.id, type='expense').all()

    return render_template('categories.html',
                           income_categories=income_categories, expense_categories=expense_categories)

@app.route('/add-category', methods=['POST'])
@login_required
def add_category():
    try:
        name = request.form.get('name')
        category_type = request.form.get('type')

        category = Category(name=name, type=category_type, user_id=current_user.id)
        db.session.add(category)
        db.session.commit()

        flash(f'{category_type.capitalize()} category added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(e)
        flash('an error occured while adding the category', 'error')
    return redirect(url_for('categories'))

@app.route('/edit-category', methods=['POST'])
@login_required
def edit_category():
    try:
        category_id = request.form.get('id')
        name = request.form.get('name')

        category = Category.query.filter_by(id=category_id, user_id = current_user.id).first_or_404()
        category.name = name

        db.session.add(category)
        db.session.commit()
        
        flash('Category updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(e)
        flash('An error occurred while updating the category', 'error')
    return redirect(url_for('categories'))


@app.route('/delete-category/<int:id>')
@login_required
def delete_category(id):
    category = Category.query.filter_by(id=id, user_id = current_user.id).first_or_404()

    try:
        # Check if there are transactions using this category
        transactions_count = Transaction.query.filter_by(category_id=id).count()
        if transactions_count > 0:
            flash(f'cannot delete category: {transactions_count} are using this category', 'warning')
            return redirect(url_for('categories'))
        
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(e)
        flash('An error occurred while deleting the category','error')
    return redirect(url_for('categories'))
    

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

