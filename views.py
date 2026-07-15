import math
from flask import Blueprint, render_template, request, redirect, url_for, session
from .database import save_job_history, get_job_history, update_job_status, get_all_users, create_user, delete_user, get_job_count
from .post_to_webkit import post_job_to_webkit
from .post_to_trabox import post_job_to_trabox

views_bp = Blueprint('views', __name__)

JOBS_PER_PAGE = 50

@views_bp.before_request
def check_authentication():
    # ログインしていない場合はログインページにリダイレクト
    if 'user_id' not in session and request.endpoint not in ['views.register_job', 'views.index', 'auth.login']:
        return redirect(url_for('auth.login'))

@views_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return redirect(url_for('views.register_job'))

@views_bp.route('/register', methods=['GET', 'POST'])
def register_job():
    if request.method == 'POST':
        # --- 🚨 デバッグチェックポイント 🚨 ---
        print("\n--- 案件登録処理開始 ---", flush=True) 

        # フォームから送信されたデータを取得
        form_data = {
            'loading_date': request.form.get('loading_date'),
            'loading_time': request.form.get('loading_time'),
            'loading_time_option': request.form.get('loading_time_option'),
            'loading_prefecture': request.form.get('loading_prefecture'),
            'loading_city': request.form.get('loading_city'),
            'loading_address': request.form.get('loading_address'),
            'unloading_date': request.form.get('unloading_date'),
            'unloading_time': request.form.get('unloading_time'),
            'unloading_time_option': request.form.get('unloading_time_option'),
            'unloading_prefecture': request.form.get('unloading_prefecture'),
            'unloading_city': request.form.get('unloading_city'),
            'unloading_address': request.form.get('unloading_address'),
            'package_type': request.form.get('package_type'),
            'consolidation_item': request.form.get('consolidation_item'),
            'transport_category': request.form.get('transport_category'),
            'item_shape': request.form.get('item_shape'),
            'weight': request.form.get('weight'),
            'vehicle_size': request.form.get('vehicle_size'),
            'desired_vehicle_type': request.form.get('desired_vehicle_type'),
            'vehicle_grade': request.form.get('vehicle_grade'),
            'required_equipment': request.form.get('required_equipment'),
            'desired_fare': request.form.get('desired_fare'),
            'fare_option': '要相談' if 'fare_consult' in request.form else '金額',
            'toll_fee': request.form.get('toll_fee'),
            'insurance': request.form.get('insurance'),
            'cases': request.form.get('cases'),
            'notes': request.form.get('notes'),
            'contact_person': request.form.get('contact_person'),
            'phone_number': request.form.get('phone_number'),
        }

        # 投稿履歴をデータベースに保存
        job_id = save_job_history(form_data, session.get('user_id'))

        # 投稿先のチェックボックスの選択状態を判定
        post_to_webkit_checked = 'post_to_webkit' in request.form
        post_to_trabox_checked = 'post_to_trabox' in request.form

        webkit_success = True
        trabox_success = True

        if post_to_webkit_checked:
            print("--- WebKIT投稿関数を呼び出します ---", flush=True) # 🚨 実行チェックポイント
            update_job_status(job_id, 'webkit', '投稿中')
            webkit_success = post_job_to_webkit(form_data)
            update_job_status(job_id, 'webkit', '成功' if webkit_success else '失敗')

        if post_to_trabox_checked:
            print("--- トラボックス投稿関数を呼び出します ---", flush=True) # 🚨 実行チェックポイント
            update_job_status(job_id, 'trabox', '投稿中')
            # trabox_success = post_job_to_trabox(form_data) # トラボックスの処理はスキップしてWebKITデバッグを優先
            update_job_status(job_id, 'trabox', '成功' if trabox_success else '失敗')

        # --- 🚨 デバッグチェックポイント 🚨 ---
        print("--- 案件登録処理終了 ---", flush=True) 

        if webkit_success and trabox_success:
            return redirect(url_for('views.success'))
        else:
            return "一部またはすべてのサイトへの投稿に失敗しました。詳細はログを確認してください。", 500

    return render_template('index.html', user_role=session.get('role', 'user'))

@views_bp.route('/history')
def history():
    # ユーザーの投稿履歴のみ表示
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * JOBS_PER_PAGE
    
    username = session.get('user_id')
    
    jobs = get_job_history(username=username, limit=JOBS_PER_PAGE, offset=offset)
    total_jobs = get_job_count(username=username)
    total_pages = math.ceil(total_jobs / JOBS_PER_PAGE)
    
    return render_template('history.html', jobs=jobs, user_role=session.get('role', 'user'), page=page, total_pages=total_pages, total_jobs=total_jobs)

# 管理者専用ルート
@views_bp.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return "管理者権限がありません", 403
    return render_template('admin/dashboard.html', user_role='admin')

@views_bp.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if session.get('role') != 'admin':
        return "管理者権限がありません", 403

    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        if action == 'create':
            password = request.form.get('password')
            role = request.form.get('role')
            create_user(username, password, role)
        elif action == 'delete':
            delete_user(username)
        return redirect(url_for('views.admin_users'))

    users = get_all_users()
    return render_template('admin/users.html', users=users, user_role='admin')

@views_bp.route('/admin/history', methods=['GET'])
def admin_history():
    if session.get('role') != 'admin':
        return "管理者権限がありません", 403
    
    # フィルター条件とページ番号を取得
    username = request.args.get('username')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * JOBS_PER_PAGE

    jobs = get_job_history(username=username, start_date=start_date, end_date=end_date, limit=JOBS_PER_PAGE, offset=offset)
    total_jobs = get_job_count(username=username, start_date=start_date, end_date=end_date)
    total_pages = math.ceil(total_jobs / JOBS_PER_PAGE)

    all_users = get_all_users()
    
    return render_template('admin/admin_history.html', jobs=jobs, all_users=all_users, user_role='admin', page=page, total_pages=total_pages, total_jobs=total_jobs)

@views_bp.route('/success')
def success():
    return render_template('success.html', user_role=session.get('role', 'user'))

@views_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('auth.login'))