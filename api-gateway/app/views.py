from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
import requests
import os
from math import ceil
import jwt
import datetime

# Service URLs - use environment variables for flexibility between Docker and local development
BOOK_SERVICE_URL = os.environ.get("BOOK_SERVICE_URL", "http://localhost:8002")
CART_SERVICE_URL = os.environ.get("CART_SERVICE_URL", "http://localhost:8003")
CUSTOMER_SERVICE_URL = os.environ.get("CUSTOMER_SERVICE_URL", "http://localhost:8001")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8004")
STAFF_SERVICE_URL = os.environ.get("STAFF_SERVICE_URL", "http://localhost:8005")
MANAGER_SERVICE_URL = os.environ.get("MANAGER_SERVICE_URL", "http://localhost:8006")
CATALOG_SERVICE_URL = os.environ.get("CATALOG_SERVICE_URL", "http://localhost:8007")
PAY_SERVICE_URL = os.environ.get("PAY_SERVICE_URL", "http://localhost:8008")
SHIP_SERVICE_URL = os.environ.get("SHIP_SERVICE_URL", "http://localhost:8009")
COMMENT_RATE_SERVICE_URL = os.environ.get("COMMENT_RATE_SERVICE_URL", "http://localhost:8010")
RECOMMENDER_SERVICE_URL = os.environ.get("RECOMMENDER_SERVICE_URL", "http://localhost:8011")
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8012")
CLOTHE_SERVICE_URL = os.environ.get("CLOTHE_SERVICE_URL", "http://localhost:8013")


# ── HELPERS ──────────────────────────────────────────────────

def is_staff_check(user):
    return user.is_staff


def _get_store_customer(request):
    cid = request.session.get("customer_id")
    if cid:
        return {"id": cid, "name": request.session.get("customer_name", "")}
    return None


def _get_jwt_token(request):
    """Extract JWT token from request session or headers"""
    token = request.session.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def _get_auth_headers(request):
    """Get authentication headers for service-to-service requests"""
    token = _get_jwt_token(request)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _generate_fallback_jwt_token(customer_id, customer_name, email=""):
    """Generate JWT token when auth service is not available"""
    try:
        secret = os.environ.get("JWT_SECRET_KEY", "bookstore-jwt-secret")
        payload = {
            'user_id': customer_id,
            'sub': str(customer_id),
            'role': 'customer',
            'email': email,
            'name': customer_name,
            'iss': 'bookstore-auth-service',
            'aud': 'bookstore-clients',
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
            'iat': datetime.datetime.utcnow()
        }
        token = jwt.encode(payload, secret, algorithm='HS256')
        return token
    except Exception:
        return None


def _get_cart_id(customer_id, request=None):
    headers = _get_auth_headers(request) if request else {}
    try:
        r = requests.get(f"{CART_SERVICE_URL}/carts/{customer_id}/", timeout=3, headers=headers)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "cart_id" in data:
                return data["cart_id"]

        # Fallback for first-time customers or transient desync: explicitly create cart.
        r_create = requests.post(
            f"{CART_SERVICE_URL}/carts/",
            json={"customer_id": customer_id},
            timeout=3,
            headers=headers,
        )
        if r_create.status_code in (200, 201):
            created = r_create.json()
            if isinstance(created, dict) and "id" in created:
                return created["id"]

        # Final retry to handle race conditions.
        r_retry = requests.get(f"{CART_SERVICE_URL}/carts/{customer_id}/", timeout=3, headers=headers)
        if r_retry.status_code == 200:
            data = r_retry.json()
            if isinstance(data, dict) and "cart_id" in data:
                return data["cart_id"]
    except Exception:
        pass
    return None


def _get_cart_count(customer_id, request=None):
    """Get total number of items in cart for displaying badge"""
    headers = _get_auth_headers(request) if request else {}
    try:
        r = requests.get(f"{CART_SERVICE_URL}/carts/{customer_id}/", timeout=3, headers=headers)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            return sum(item.get("quantity", 1) for item in items)
    except Exception:
        pass
    return 0


# ── ADMIN VIEWS ──────────────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def home(request):
    try:
        books = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3).json()
    except Exception:
        books = []
    try:
        customers = requests.get(f"{CUSTOMER_SERVICE_URL}/customers/", timeout=3).json()
    except Exception:
        customers = []
    try:
        orders = requests.get(f"{ORDER_SERVICE_URL}/orders/", timeout=3).json()
    except Exception:
        orders = []
    try:
        staff = requests.get(f"{STAFF_SERVICE_URL}/staff/", timeout=3).json()
    except Exception:
        staff = []
    try:
        managers = requests.get(f"{MANAGER_SERVICE_URL}/managers/", timeout=3).json()
    except Exception:
        managers = []
    try:
        payments = requests.get(f"{PAY_SERVICE_URL}/payments/", timeout=3).json()
    except Exception:
        payments = []
    try:
        shipments = requests.get(f"{SHIP_SERVICE_URL}/shipments/", timeout=3).json()
    except Exception:
        shipments = []
    return render(request, "home.html", {
        "total_books": len(books) if isinstance(books, list) else 0,
        "total_customers": len(customers) if isinstance(customers, list) else 0,
        "total_orders": len(orders) if isinstance(orders, list) else 0,
        "total_staff": len(staff) if isinstance(staff, list) else 0,
        "total_managers": len(managers) if isinstance(managers, list) else 0,
        "total_payments": len(payments) if isinstance(payments, list) else 0,
        "total_shipments": len(shipments) if isinstance(shipments, list) else 0,
    })


@user_passes_test(is_staff_check, login_url='/admin/login/')
def book_list(request):
    error = None
    books = []
    if request.method == "POST":
        data = {
            "title": request.POST.get("title"),
            "author": request.POST.get("author"),
            "price": request.POST.get("price"),
            "stock": request.POST.get("stock"),
        }
        try:
            r = requests.post(f"{BOOK_SERVICE_URL}/books/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm sách thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Không kết nối được book-service: {e}")
        return redirect("book_list")
    try:
        r = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3)
        books = r.json()
        if not isinstance(books, list):
            books = []
    except Exception as e:
        error = str(e)
    return render(request, "books.html", {"books": books, "error": error})


@user_passes_test(is_staff_check, login_url='/admin/login/')
def customer_list(request):
    error = None
    customers = []
    if request.method == "POST":
        data = {
            "name": request.POST.get("name"),
            "email": request.POST.get("email"),
        }
        try:
            r = requests.post(f"{CUSTOMER_SERVICE_URL}/customers/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm khách hàng thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Không kết nối được customer-service: {e}")
        return redirect("customer_list")
    try:
        r = requests.get(f"{CUSTOMER_SERVICE_URL}/customers/", timeout=3)
        customers = r.json()
        if not isinstance(customers, list):
            customers = []
    except Exception as e:
        error = str(e)
    return render(request, "customers.html", {"customers": customers, "error": error})


@user_passes_test(is_staff_check, login_url='/admin/login/')
def view_cart(request, customer_id):
    error = None
    items = []
    cart_id = None
    cart_error = None
    if request.method == "POST":
        data = {
            "cart": request.POST.get("cart_id"),
            "book_id": request.POST.get("book_id"),
            "quantity": request.POST.get("quantity"),
        }
        try:
            headers = _get_auth_headers(request)
            r = requests.post(f"{CART_SERVICE_URL}/cart-items/", json=data, timeout=3, headers=headers)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm vào giỏ hàng thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Không kết nối được cart-service: {e}")
        return redirect("view_cart", customer_id=customer_id)
    try:
        headers = _get_auth_headers(request)
        r = requests.get(f"{CART_SERVICE_URL}/carts/{customer_id}/", timeout=3, headers=headers)
        data = r.json()
        if isinstance(data, dict) and "cart_id" in data:
            cart_id = data["cart_id"]
            items = data.get("items", [])
        elif isinstance(data, dict) and "error" in data:
            cart_error = data["error"]
    except Exception as e:
        error = str(e)
    try:
        books = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3).json()
        if not isinstance(books, list):
            books = []
    except Exception:
        books = []
    return render(request, "cart.html", {
        "items": items, "customer_id": customer_id, "cart_id": cart_id,
        "books": books, "error": error, "cart_error": cart_error,
    })


# ── STOREFRONT VIEWS ─────────────────────────────────────────

def store_home(request):
    books = []
    recommendations = []
    q = request.GET.get("q", "").strip()
    author = request.GET.get("author", "").strip()
    stock = request.GET.get("stock", "all").strip()
    sort = request.GET.get("sort", "featured").strip()
    min_price_raw = request.GET.get("min_price", "").strip()
    max_price_raw = request.GET.get("max_price", "").strip()
    page_raw = request.GET.get("page", "1").strip()

    min_price = None
    max_price = None
    try:
        if min_price_raw:
            min_price = float(min_price_raw)
    except ValueError:
        min_price = None
    try:
        if max_price_raw:
            max_price = float(max_price_raw)
    except ValueError:
        max_price = None

    try:
        page = max(1, int(page_raw))
    except ValueError:
        page = 1

    try:
        r = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3)
        books = r.json()
        if not isinstance(books, list):
            books = []
    except Exception:
        pass

    all_authors = sorted({str(b.get("author", "")).strip() for b in books if b.get("author")})

    filtered_books = []
    q_lower = q.lower()
    author_lower = author.lower()
    for book in books:
        title = str(book.get("title", ""))
        writer = str(book.get("author", ""))
        stock_value = int(book.get("stock", 0) or 0)
        try:
            price_value = float(book.get("price", 0) or 0)
        except (TypeError, ValueError):
            price_value = 0.0

        if q_lower and q_lower not in title.lower() and q_lower not in writer.lower():
            continue
        if author_lower and author_lower != writer.lower():
            continue
        if stock == "in_stock" and stock_value <= 0:
            continue
        if stock == "out_of_stock" and stock_value > 0:
            continue
        if min_price is not None and price_value < min_price:
            continue
        if max_price is not None and price_value > max_price:
            continue
        filtered_books.append(book)

    if sort == "price_asc":
        filtered_books.sort(key=lambda x: float(x.get("price", 0) or 0))
    elif sort == "price_desc":
        filtered_books.sort(key=lambda x: float(x.get("price", 0) or 0), reverse=True)
    elif sort == "title_asc":
        filtered_books.sort(key=lambda x: str(x.get("title", "")).lower())
    elif sort == "title_desc":
        filtered_books.sort(key=lambda x: str(x.get("title", "")).lower(), reverse=True)
    elif sort == "newest":
        filtered_books.sort(key=lambda x: int(x.get("id", 0) or 0), reverse=True)
    else:
        # Featured: in-stock first, then high stock, then newest.
        filtered_books.sort(
            key=lambda x: (
                int((x.get("stock", 0) or 0) <= 0),
                -int(x.get("stock", 0) or 0),
                -int(x.get("id", 0) or 0),
            )
        )

    page_size = 12
    total_results = len(filtered_books)
    total_pages = max(1, ceil(total_results / page_size))
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    paginated_books = filtered_books[start:end]

    base_filters = request.GET.copy()
    if "page" in base_filters:
        del base_filters["page"]
    query_without_page = base_filters.urlencode()

    page_numbers = [
        n for n in range(max(1, page - 2), min(total_pages, page + 2) + 1)
    ]

    current_querystring = request.get_full_path()

    customer = _get_store_customer(request)
    cart_count = 0
    if customer:
        cart_count = _get_cart_count(customer["id"], request)
        try:
            r = requests.get(f"{RECOMMENDER_SERVICE_URL}/recommendations/{customer['id']}/", timeout=5)
            if r.status_code == 200:
                recommendations = r.json().get("recommendations", [])
        except Exception:
            pass
    return render(request, "store_home.html", {
        "books": paginated_books,
        "customer": customer,
        "cart_count": cart_count,
        "recommendations": recommendations,
        "authors": all_authors,
        "total_books": len(books),
        "total_results": total_results,
        "in_stock_count": sum(1 for b in books if int(b.get("stock", 0) or 0) > 0),
        "filters": {
            "q": q,
            "author": author,
            "stock": stock,
            "sort": sort,
            "min_price": min_price_raw,
            "max_price": max_price_raw,
        },
        "page": page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "page_numbers": page_numbers,
        "query_without_page": query_without_page,
        "current_querystring": current_querystring,
    })


def store_login(request):
    if _get_store_customer(request):
        return redirect("store_home")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        try:
            r = requests.post(f"{CUSTOMER_SERVICE_URL}/customers/login/", 
                              json={"email": email, "password": password}, timeout=3)
            if r.status_code == 200:
                try:
                    found = r.json()
                    request.session["customer_id"] = found["id"]
                    request.session["customer_name"] = found["name"]

                    # Central auth-service token issuance.
                    access_token = None
                    try:
                        r_auth = requests.post(
                            f"{AUTH_SERVICE_URL}/auth/login/",
                            json={"email": email, "password": password},
                            timeout=3,
                        )
                        if r_auth.status_code == 200:
                            access_token = r_auth.json().get("access", "")
                    except Exception:
                        pass

                    # Fallback: generate JWT token when auth service fails or returns error
                    if not access_token:
                        access_token = _generate_fallback_jwt_token(
                            found["id"],
                            found["name"],
                            email
                        )

                    if access_token:
                        request.session["access_token"] = access_token

                    messages.success(request, f"Xin chào, {found['name']}!")
                    return redirect("store_home")
                except ValueError:
                    messages.error(request, "Lỗi phản hồi từ hệ thống xác thực (Invalid JSON).")
            else:
                try:
                    error_msg = r.json().get("error", "Email hoặc mật khẩu không đúng.")
                except ValueError:
                    error_msg = f"Lỗi hệ thống ({r.status_code}). Vui lòng thử lại sau."
                messages.error(request, error_msg)
        except Exception as e:
            messages.error(request, f"Lỗi kết nối: {e}")
    return render(request, "store_login.html", {"customer": None})


def store_register(request):
    if _get_store_customer(request):
        return redirect("store_home")
    if request.method == "POST":
        data = {
            "name": request.POST.get("name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "password": request.POST.get("password", ""),
        }
        try:
            r = requests.post(f"{CUSTOMER_SERVICE_URL}/customers/", json=data, timeout=3)
            if r.status_code in (200, 201):
                customer = r.json()

                # Sync identity to central auth-service.
                access_token = None
                try:
                    r_auth = requests.post(
                        f"{AUTH_SERVICE_URL}/auth/register/",
                        json={
                            "email": data["email"],
                            "password": data["password"],
                            "role": "customer",
                        },
                        timeout=3,
                    )
                    if r_auth.status_code in (200, 201):
                        access_token = r_auth.json().get("access", "")
                except Exception:
                    pass

                # Fallback: generate JWT token when auth service fails
                if not access_token:
                    access_token = _generate_fallback_jwt_token(
                        customer["id"],
                        customer["name"],
                        data["email"]
                    )

                if access_token:
                    request.session["access_token"] = access_token

                # Log them in automatically
                request.session["customer_id"] = customer["id"]
                request.session["customer_name"] = customer["name"]
                messages.success(request, f"Đăng ký thành công! Xin chào, {customer['name']}!")
                return redirect("store_home")
            else:
                resp = r.json()
                if "email" in resp:
                    messages.error(request, "Email này đã được đăng ký.")
                else:
                    messages.error(request, f"Lỗi: {resp}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối: {e}")
    return render(request, "store_register.html", {"customer": None})


def store_profile(request):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    
    if request.method == "POST":
        data = {
            "name": request.POST.get("name"),
            "phone": request.POST.get("phone"),
            "job_id": request.POST.get("job_id"),
        }
        try:
            r = requests.patch(f"{CUSTOMER_SERVICE_URL}/customers/{customer['id']}/", json=data, timeout=3)
            if r.status_code == 200:
                messages.success(request, "Cập nhật hồ sơ thành công!")
                request.session["customer_name"] = data["name"] # Sync name in session
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối: {e}")
        return redirect("store_profile")

    # Fetch customer full info and available jobs
    full_info = {}
    jobs = []
    try:
        r_cust = requests.get(f"{CUSTOMER_SERVICE_URL}/customers/{customer['id']}/", timeout=3)
        if r_cust.status_code == 200:
            full_info = r_cust.json()
        
        r_jobs = requests.get(f"{CUSTOMER_SERVICE_URL}/jobs/", timeout=3)
        if r_jobs.status_code == 200:
            jobs = r_jobs.json()
    except Exception as e:
        messages.error(request, f"Lỗi lấy thông tin: {e}")

    cart_count = _get_cart_count(customer['id'], request)
    return render(request, "store_profile.html", {
        "customer": full_info,
        "jobs": jobs,
        "cart_count": cart_count,
    })


def store_logout(request):
    request.session.flush()
    messages.success(request, "Đã đăng xuất thành công.")
    return redirect("store_home")


def store_cart(request):
    customer = _get_store_customer(request)
    if not customer:
        messages.error(request, "Vui lòng đăng nhập để xem giỏ hàng.")
        return redirect("store_login")
    items = []
    cart_id = None
    error = None
    try:
        headers = _get_auth_headers(request)
        r = requests.get(f"{CART_SERVICE_URL}/carts/{customer['id']}/", timeout=3, headers=headers)
        data = r.json()
        if isinstance(data, dict) and "cart_id" in data:
            cart_id = data["cart_id"]
            items = data.get("items", [])
        elif isinstance(data, dict) and "error" in data:
            error = data["error"]
    except Exception as e:
        error = str(e)
        
    books_map = {}
    clothes_map = {}
    try:
        books = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3).json()
        if isinstance(books, list):
            books_map = {b["id"]: b for b in books}
            
        clothes = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=3).json()
        if isinstance(clothes, list):
            clothes_map = {c["id"]: c for c in clothes}
    except Exception:
        pass
        
    total = 0
    enriched = []
    for item in items:
        actual_id = item["book_id"]
        if actual_id > 1000000:
            clothe_id = actual_id - 1000000
            clothe = clothes_map.get(clothe_id, {"name": f"Áo #{clothe_id}", "price": 0})
            subtotal = float(clothe.get("price", 0)) * item["quantity"]
            total += subtotal
            enriched.append({
                **item, 
                "book": {"title": clothe.get("name"), "author": "Thời trang", "price": clothe.get("price")}, 
                "subtotal": subtotal,
                "is_clothe": True
            })
        else:
            book = books_map.get(actual_id, {"title": f"Sách #{actual_id}", "author": "", "price": 0})
            subtotal = float(book.get("price", 0)) * item["quantity"]
            total += subtotal
            enriched.append({**item, "book": book, "subtotal": subtotal, "is_clothe": False})

    cart_count = sum(item["quantity"] for item in enriched)
    return render(request, "store_cart.html", {
        "items": enriched, "cart_id": cart_id,
        "total": total, "error": error, "customer": customer,
        "cart_count": cart_count,
    })


def store_add_to_cart(request):
    if request.method != "POST":
        return redirect("store_home")

    next_url = request.POST.get("next", "/store/")
    if not next_url.startswith("/store"):
        next_url = "/store/"

    customer = _get_store_customer(request)
    if not customer:
        messages.error(request, "Vui lòng đăng nhập để thêm vào giỏ hàng.")
        return redirect("store_login")

    book_id = request.POST.get("book_id")
    clothe_id = request.POST.get("clothe_id")
    
    try:
        quantity = int(request.POST.get("quantity", 1))
    except ValueError:
        quantity = 1
    quantity = max(1, min(quantity, 99))

    cart_id = _get_cart_id(customer["id"], request)
    if not cart_id:
        messages.error(request, "Không tìm thấy giỏ hàng.")
        return redirect(next_url)

    if book_id and book_id != "None" and book_id != "":
        try:
            r_book = requests.get(f"{BOOK_SERVICE_URL}/books/{int(book_id)}/", timeout=3)
            if r_book.status_code == 200:
                book = r_book.json()
                if int(book.get("stock", 0) or 0) <= 0:
                    messages.error(request, f"Sách '{book.get('title', '')}' đã hết hàng.")
                    return redirect(next_url)
            else:
                messages.error(request, "Không thể kiểm tra tồn kho hiện tại.")
                return redirect(next_url)
        except Exception as e:
            messages.error(request, f"Lỗi kết nối kiểm tra tồn kho: {e}")
            return redirect(next_url)
        try:
            headers = _get_auth_headers(request)
            r = requests.post(f"{CART_SERVICE_URL}/cart-items/", json={
                "cart": cart_id,
                "book_id": int(book_id),
                "quantity": quantity,
            }, timeout=3, headers=headers)
            if r.status_code in (200, 201):
                messages.success(request, "Đã thêm Sách vào giỏ hàng!")
            else:
                messages.error(request, f"Lỗi thêm vào giỏ: {r.text}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối giỏ hàng: {e}")
            
    elif clothe_id and clothe_id != "None" and clothe_id != "":
        try:
            r_clothe = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/{int(clothe_id)}/", timeout=3)
            if r_clothe.status_code == 200:
                clothe = r_clothe.json()
                if int(clothe.get("stock", 0) or 0) <= 0:
                    messages.error(request, f"Sản phẩm '{clothe.get('name', '')}' đã hết hàng.")
                    return redirect(next_url)
            else:
                messages.error(request, "Không thể kiểm tra tồn kho hiện tại.")
                return redirect(next_url)
        except Exception as e:
            messages.error(request, f"Lỗi kết nối kiểm tra tồn kho: {e}")
            return redirect(next_url)
        try:
            headers = _get_auth_headers(request)
            r = requests.post(f"{CART_SERVICE_URL}/cart-items/", json={
                "cart": cart_id,
                "book_id": int(clothe_id) + 1000000,
                "quantity": quantity,
            }, timeout=3, headers=headers)
            if r.status_code in (200, 201):
                messages.success(request, "Đã thêm Quần áo vào giỏ hàng!")
            else:
                messages.error(request, f"Lỗi thêm vào giỏ: {r.text}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối giỏ hàng: {e}")
    else:
        messages.error(request, "Dữ liệu sản phẩm không hợp lệ.")

    return redirect(next_url)


def store_book_detail(request, book_id):
    book = None
    reviews_data = {"reviews": [], "average_rating": 0, "total_reviews": 0}
    try:
        # Fetch single book directly from book-service
        r = requests.get(f"{BOOK_SERVICE_URL}/books/{book_id}/", timeout=3)
        if r.status_code == 200:
            book = r.json()
    except Exception as e:
        print(f"Error fetching book detail: {e}")
    
    try:
        r = requests.get(f"{COMMENT_RATE_SERVICE_URL}/reviews/book/{book_id}/", timeout=3)
        if r.status_code == 200:
            reviews_data = r.json()
    except Exception:
        pass

    customer = _get_store_customer(request)
    cart_count = _get_cart_count(customer["id"], request) if customer else 0
    return render(request, "store_book_detail.html", {
        "book": book,
        "customer": customer,
        "cart_count": cart_count,
        "reviews": reviews_data.get("reviews", []),
        "average_rating": reviews_data.get("average_rating", 0),
        "total_reviews": reviews_data.get("total_reviews", 0),
    })


def store_remove_from_cart(request, book_id):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    cart_id = _get_cart_id(customer["id"], request)
    if cart_id:
        try:
            headers = _get_auth_headers(request)
            requests.delete(f"{CART_SERVICE_URL}/cart-items/{cart_id}/{book_id}/", timeout=3, headers=headers)
            messages.success(request, "Đã xóa sản phẩm khỏi giỏ hàng.")
        except Exception as e:
            messages.error(request, f"Lỗi: {e}")
    return redirect("store_cart")


def store_checkout(request):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    
    if request.method != "POST":
        return redirect("store_cart")

    # 1. Get cart items
    try:
        headers = _get_auth_headers(request)
        r_cart = requests.get(f"{CART_SERVICE_URL}/carts/{customer['id']}/", timeout=3, headers=headers)
        cart_data = r_cart.json()
        raw_items = cart_data.get("items", [])
    except Exception as e:
        messages.error(request, f"Lỗi lấy thông tin giỏ hàng: {e}")
        return redirect("store_cart")

    if not raw_items:
        messages.error(request, "Giỏ hàng trống.")
        return redirect("store_home")

    # 2. Pre-check stock and gather prices
    items_to_order = []
    total_price = 0
    try:
        books_r = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3)
        books_map = {b["id"]: b for b in books_r.json()}
        
        # Only fetch clothes if there are clothe items in cart
        has_clothes = any(ri["book_id"] > 1000000 for ri in raw_items)
        clothes_map = {}
        if has_clothes:
            try:
                clothes_r = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=3)
                clothes_map = {c["id"]: c for c in clothes_r.json()}
            except Exception:
                messages.error(request, "Không thể kết nối đến dịch vụ quần áo.")
                return redirect("store_cart")
        
        for ri in raw_items:
            actual_id = ri["book_id"]
            if actual_id > 1000000:
                c_id = actual_id - 1000000
                clothe = clothes_map.get(c_id)
                if not clothe:
                    messages.error(request, f"Quần áo #{c_id} không tồn tại.")
                    return redirect("store_cart")
                if clothe["stock"] < ri["quantity"]:
                    messages.error(request, f"Sản phẩm '{clothe['name']}' không đủ hàng (Còn lại: {clothe['stock']}).")
                    return redirect("store_cart")
                price = float(clothe["price"])
                items_to_order.append({
                    "book_id": actual_id, # Giữ nguyên ID mapping để order lưu
                    "quantity": ri["quantity"],
                    "price": price,
                    "title": clothe["name"],
                    "is_clothe": True,
                    "real_id": c_id
                })
                total_price += price * ri["quantity"]
            else:
                book = books_map.get(actual_id)
                if not book:
                    messages.error(request, f"Sách #{actual_id} không tồn tại.")
                    return redirect("store_cart")
                if book["stock"] < ri["quantity"]:
                    messages.error(request, f"Sách '{book['title']}' không đủ hàng (Còn lại: {book['stock']}).")
                    return redirect("store_cart")
                price = float(book["price"])
                items_to_order.append({
                    "book_id": actual_id,
                    "quantity": ri["quantity"],
                    "price": price,
                    "title": book["title"],
                    "is_clothe": False,
                    "real_id": actual_id
                })
                total_price += price * ri["quantity"]
    except Exception as e:
        messages.error(request, f"Lỗi kiểm tra kho: {e}")
        return redirect("store_cart")

    # 3. Reduce stock first
    reduced_items = []
    stock_failed = False
    for item in items_to_order:
        try:
            if item.get("is_clothe"):
                res = requests.post(f"{CLOTHE_SERVICE_URL}/clothes/{item['real_id']}/reduce-stock/", 
                                    json={"quantity": item["quantity"]}, timeout=3)
            else:
                res = requests.post(f"{BOOK_SERVICE_URL}/books/{item['real_id']}/reduce-stock/", 
                                    json={"quantity": item["quantity"]}, timeout=3)
                                    
            if res.status_code == 200:
                reduced_items.append(item)
            else:
                stock_failed = True
                error_msg = res.json().get("error", "Lỗi không xác định")
                messages.error(request, f"Không thể trừ kho cho '{item['title']}': {error_msg}")
                break
        except Exception as e:
            stock_failed = True
            messages.error(request, f"Lỗi kết nối khi trừ kho: {e}")
            break

    if stock_failed:
        # Rollback
        for ri in reduced_items:
            try:
                if ri.get("is_clothe"):
                    requests.post(f"{CLOTHE_SERVICE_URL}/clothes/{ri['real_id']}/restore-stock/", json={"quantity": ri["quantity"]}, timeout=3)
                else:
                    requests.post(f"{BOOK_SERVICE_URL}/books/{ri['real_id']}/restore-stock/", json={"quantity": ri["quantity"]}, timeout=3)
            except Exception:
                pass
        return redirect("store_cart")

    # 4. Create the Order
    province = request.POST.get("province", "Khác")
    address_detail = request.POST.get("address_detail", "")
    full_address = f"{address_detail}, {province}"
    payment_method = request.POST.get("payment_method", "cod")
    
    shipping_fee = 0
    if province not in ["Hà Nội", "Hồ Chí Minh"]:
        shipping_fee = 30000
    
    order_data = {
        "customer_id": customer["id"],
        "total_price": total_price,
        "shipping_fee": shipping_fee,
        "shipping_address": full_address,
        "payment_method": payment_method,
        "items": [{"book_id": i["book_id"], "quantity": i["quantity"], "price": i["price"]} for i in items_to_order]
    }
    
    try:
        r_order = requests.post(f"{ORDER_SERVICE_URL}/orders/", json=order_data, timeout=5)
        if r_order.status_code == 201:
            order_resp = r_order.json()

            # 5. Clear cart
            try:
                headers = _get_auth_headers(request)
                requests.delete(f"{CART_SERVICE_URL}/carts/{customer['id']}/clear/", timeout=3, headers=headers)
            except Exception:
                pass
            
            # 6. VNPay Simulation
            if payment_method == 'vnpay':
                try:
                    pay_res = requests.post(f"{PAY_SERVICE_URL}/payments/", json={
                        "order_id": order_resp.get("id"),
                        "customer_id": customer["id"],
                        "amount": order_resp.get("grand_total"),
                        "method": "vnpay",
                    }, timeout=3, headers=headers)
                    if pay_res.status_code == 201:
                        pay_data = pay_res.json()
                        return render(request, "store_vnpay_sim.html", {
                            "order": order_resp,
                            "payment": pay_data
                        })
                except Exception:
                    pass

            messages.success(request, "Đặt hàng thành công! Hệ thống Saga đang xử lý đơn hàng của bạn.")
            return render(request, "store_success.html", {"customer": customer, "order": order_resp})

        else:
            # Rollback
            for ri in reduced_items:
                try:
                    if ri.get("is_clothe"):
                        requests.post(f"{CLOTHE_SERVICE_URL}/clothes/{ri['real_id']}/restore-stock/", json={"quantity": ri["quantity"]}, timeout=3)
                    else:
                        requests.post(f"{BOOK_SERVICE_URL}/books/{ri['real_id']}/restore-stock/", json={"quantity": ri["quantity"]}, timeout=3)
                except Exception:
                    pass
            messages.error(request, f"Lỗi tạo đơn hàng: {r_order.text}")
    except Exception as e:
        for ri in reduced_items:
            try:
                if ri.get("is_clothe"):
                    requests.post(f"{CLOTHE_SERVICE_URL}/clothes/{ri['real_id']}/restore-stock/", json={"quantity": ri["quantity"]}, timeout=3)
                else:
                    requests.post(f"{BOOK_SERVICE_URL}/books/{ri['real_id']}/restore-stock/", json={"quantity": ri["quantity"]}, timeout=3)
            except Exception:
                pass
        messages.error(request, f"Lỗi kết nối order-service: {e}")
    
    return redirect("store_cart")

    # 1. Get cart items
    try:
        headers = _get_auth_headers(request)
        r_cart = requests.get(f"{CART_SERVICE_URL}/carts/{customer['id']}/", timeout=3, headers=headers)
        cart_data = r_cart.json()
        raw_items = cart_data.get("items", [])
    except Exception as e:
        messages.error(request, f"Lỗi lấy thông tin giỏ hàng: {e}")
        return redirect("store_cart")

    if not raw_items:
        messages.error(request, "Giỏ hàng trống.")
        return redirect("store_home")

    # 2. Pre-check stock and gather prices
    items_to_order = []
    total_price = 0
    try:
        books_r = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3)
        books_map = {b["id"]: b for b in books_r.json()}
        
        for ri in raw_items:
            book = books_map.get(ri["book_id"])
            if not book:
                messages.error(request, f"Sách #{ri['book_id']} không tồn tại.")
                return redirect("store_cart")
            
            if book["stock"] < ri["quantity"]:
                messages.error(request, f"Sách '{book['title']}' không đủ hàng (Còn lại: {book['stock']}).")
                return redirect("store_cart")
            
            price = float(book["price"])
            items_to_order.append({
                "book_id": ri["book_id"],
                "quantity": ri["quantity"],
                "price": price,
                "title": book["title"]
            })
            total_price += price * ri["quantity"]
    except Exception as e:
        messages.error(request, f"Lỗi kiểm tra kho: {e}")
        return redirect("store_cart")

    # 3. Reduce stock first (Professional approach: reserve/deduct before confirming order)
    reduced_items = []
    stock_failed = False
    for item in items_to_order:
        try:
            res = requests.post(f"{BOOK_SERVICE_URL}/books/{item['book_id']}/reduce-stock/", 
                                json={"quantity": item["quantity"]}, timeout=3)
            if res.status_code == 200:
                reduced_items.append(item)
            else:
                stock_failed = True
                error_msg = res.json().get("error", "Lỗi không xác định")
                messages.error(request, f"Không thể trừ kho cho '{item['title']}': {error_msg}")
                break
        except Exception as e:
            stock_failed = True
            messages.error(request, f"Lỗi kết nối khi trừ kho: {e}")
            break

    # If stock reduction failed mid-way, in a perfect world we would roll back (increase stock back).
    # For this project, we'll stop and notify the user.
    if stock_failed:
        # Simple rollback for already reduced items
        for ri in reduced_items:
            try:
                # We can't use reduce-stock with negative, so we use patch if available or just leave it.
                # Since book-service patch exists, we could use it to add back.
                book_r = requests.get(f"{BOOK_SERVICE_URL}/books/{ri['book_id']}/", timeout=3)
                curr_stock = book_r.json().get("stock", 0)
                requests.patch(f"{BOOK_SERVICE_URL}/books/{ri['book_id']}/", 
                               json={"stock": curr_stock + ri["quantity"]}, timeout=3)
            except Exception:
                pass
        return redirect("store_cart")

    # 4. Create the Order
    province = request.POST.get("province", "Khác")
    address_detail = request.POST.get("address_detail", "")
    full_address = f"{address_detail}, {province}"
    payment_method = request.POST.get("payment_method", "cod")
    
    # Simple shipping fee logic
    shipping_fee = 0
    if province not in ["Hà Nội", "Hồ Chí Minh"]:
        shipping_fee = 30000
    
    order_data = {
        "customer_id": customer["id"],
        "total_price": total_price,
        "shipping_fee": shipping_fee,
        "shipping_address": full_address,
        "payment_method": payment_method,
        "items": items_to_order
    }
    
    try:
        r_order = requests.post(f"{ORDER_SERVICE_URL}/orders/", json=order_data, timeout=5)
        if r_order.status_code == 201:
            order_resp = r_order.json()

            # 5. Clear cart using the new endpoint
            try:
                headers = _get_auth_headers(request)
                requests.delete(f"{CART_SERVICE_URL}/carts/{customer['id']}/clear/", timeout=3, headers=headers)
            except Exception:
                pass
            
            # 6. VNPay Simulation Logic
            if payment_method == 'vnpay':
                # Create a temporary payment record first
                try:
                    pay_res = requests.post(f"{PAY_SERVICE_URL}/payments/", json={
                        "order_id": order_resp.get("id"),
                        "customer_id": customer["id"],
                        "amount": order_resp.get("grand_total"),
                        "method": "vnpay",
                    }, timeout=3, headers=headers)
                    if pay_res.status_code == 201:
                        pay_data = pay_res.json()
                        # Redirect to simulation page
                        return render(request, "store_vnpay_sim.html", {
                            "order": order_resp,
                            "payment": pay_data
                        })
                except Exception:
                    pass

            messages.success(request, "Đặt hàng thành công! Hệ thống Saga đang xử lý đơn hàng của bạn.")
            return render(request, "store_success.html", {"customer": customer, "order": order_resp})

        else:
            # If order creation fails, we MUST roll back stock
            for ri in reduced_items:
                try:
                    book_r = requests.get(f"{BOOK_SERVICE_URL}/books/{ri['book_id']}/", timeout=3)
                    curr_stock = book_r.json().get("stock", 0)
                    requests.patch(f"{BOOK_SERVICE_URL}/books/{ri['book_id']}/", 
                                   json={"stock": curr_stock + ri["quantity"]}, timeout=3)
                except Exception:
                    pass
            messages.error(request, f"Lỗi tạo đơn hàng: {r_order.text}")
    except Exception as e:
        # Roll back stock on connection error
        for ri in reduced_items:
            try:
                book_r = requests.get(f"{BOOK_SERVICE_URL}/books/{ri['book_id']}/", timeout=3)
                curr_stock = book_r.json().get("stock", 0)
                requests.patch(f"{BOOK_SERVICE_URL}/books/{ri['book_id']}/", 
                               json={"stock": curr_stock + ri["quantity"]}, timeout=3)
            except Exception:
                pass
        messages.error(request, f"Lỗi kết nối order-service: {e}")
    
    return redirect("store_cart")


def store_orders(request):
    customer = _get_store_customer(request)
    if not customer:
        messages.error(request, "Vui lòng đăng nhập để xem đơn hàng.")
        return redirect("store_login")
    orders = []
    try:
        r = requests.get(f"{ORDER_SERVICE_URL}/orders/customer/{customer['id']}/", timeout=5)
        orders = r.json()
        if not isinstance(orders, list):
            orders = []
    except Exception:
        pass
    cart_count = _get_cart_count(customer['id'], request)
    return render(request, "store_orders.html", {
        "orders": orders,
        "customer": customer,
        "cart_count": cart_count,
    })


def store_order_detail(request, order_id):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    order = None
    shipment = None
    payment = None
    try:
        r = requests.get(f"{ORDER_SERVICE_URL}/orders/{order_id}/", timeout=5)
        if r.status_code == 200:
            order = r.json()
            if order.get("customer_id") != customer["id"]:
                messages.error(request, "Bạn không có quyền xem đơn hàng này.")
                return redirect("store_orders")
            # Enrich items with book info
            books_map = {}
            clothes_map = {}
            try:
                books = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3).json()
                if isinstance(books, list):
                    books_map = {b["id"]: b for b in books}
            except Exception:
                pass
            try:
                clothes = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=3).json()
                if isinstance(clothes, list):
                    clothes_map = {c["id"]: c for c in clothes}
            except Exception:
                pass
            for item in order.get("items", []):
                actual_id = item.get("book_id")
                if isinstance(actual_id, int) and actual_id > 1000000:
                    clothe_id = actual_id - 1000000
                    clothe = clothes_map.get(clothe_id, {})
                    item["book_title"] = clothe.get("name", f"Quần áo #{clothe_id}")
                    item["book_author"] = clothe.get("material", "Thời trang")
                    item["image_url"] = f"https://loremflickr.com/100/140/fashion,clothes?lock={clothe_id}"
                else:
                    book = books_map.get(actual_id, {})
                    item["book_title"] = book.get("title", f"Sách #{actual_id}")
                    item["book_author"] = book.get("author", "")
                    item["image_url"] = f"https://loremflickr.com/100/140/book?lock={actual_id}"
            # Get shipment info
            try:
                r_ship = requests.get(f"{SHIP_SERVICE_URL}/shipments/order/{order_id}/", timeout=3)
                if r_ship.status_code == 200:
                    shipment = r_ship.json()
            except Exception:
                pass
            # Get payment info
            try:
                r_pay = requests.get(f"{PAY_SERVICE_URL}/payments/order/{order_id}/", timeout=3)
                if r_pay.status_code == 200:
                    pay_data = r_pay.json()
                    if isinstance(pay_data, list) and pay_data:
                        payment = pay_data[0]
            except Exception:
                pass
    except Exception:
        pass
    cart_count = _get_cart_count(customer['id'], request)
    return render(request, "store_order_detail.html", {
        "order": order,
        "customer": customer,
        "cart_count": cart_count,
        "shipment": shipment,
        "payment": payment,
    })


def store_cancel_order(request, order_id):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    
    if request.method == "POST":
        try:
            # Gửi yêu cầu DELETE sang order-service để hủy đơn và hoàn kho
            r = requests.delete(f"{ORDER_SERVICE_URL}/orders/{order_id}/", timeout=5)
            if r.status_code == 200:
                messages.success(request, "Đã hủy đơn hàng thành công và hệ thống đang hoàn lại sách vào kho.")
            else:
                resp = r.json()
                error_msg = resp.get("error", "Không thể hủy đơn hàng lúc này.")
                messages.error(request, f"Lỗi: {error_msg}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối khi hủy đơn: {e}")
            
    return redirect("store_order_detail", order_id=order_id)

def store_payment_simulate(request, order_id):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    
    try:
        # 1. Get transaction info from pay-service
        r_pay_list = requests.get(f"{PAY_SERVICE_URL}/payments/order/{order_id}/", timeout=3)
        if r_pay_list.status_code == 200:
            payments = r_pay_list.json()
            if payments:
                pay = payments[0]
                # 2. CALL THE NEW SECURE WEBHOOK (Production approach)
                requests.post(f"{PAY_SERVICE_URL}/payments/confirm-payment/", 
                               json={
                                   "order_id": order_id,
                                   "transaction_id": pay["transaction_id"],
                                   "secure_token": "SECRET_PAYMENT_TOKEN" # In real life, this is a calculated signature
                               }, timeout=3, headers=headers)
                
                messages.success(request, "Thanh toán thành công! Hệ thống đang xử lý vận chuyển.")
            else:
                messages.error(request, "Không tìm thấy thông tin thanh toán cho đơn hàng này.")
        else:
            messages.error(request, "Lỗi kết nối tới dịch vụ thanh toán.")
    except Exception as e:
        messages.error(request, f"Lỗi xử lý thanh toán: {e}")
    
    return redirect("store_order_detail", order_id=order_id)


def store_confirm_receipt(request, order_id):
    customer = _get_store_customer(request)
    if not customer:
        return redirect("store_login")
    
    try:
        # 1. Update order status to delivered
        requests.patch(f"{ORDER_SERVICE_URL}/orders/{order_id}/", 
                       json={"status": "delivered"}, timeout=5)
        
        # 2. Update shipment status to delivered
        r_ship = requests.get(f"{SHIP_SERVICE_URL}/shipments/order/{order_id}/", timeout=3)
        if r_ship.status_code == 200:
            shipment = r_ship.json()
            ship_id = shipment["id"]
            requests.patch(f"{SHIP_SERVICE_URL}/shipments/{ship_id}/", 
                           json={"status": "delivered"}, timeout=3)
        
        messages.success(request, "Xác nhận nhận hàng thành công. Bạn có thể để lại đánh giá cho sản phẩm.")
    except Exception as e:
        messages.error(request, f"Lỗi xác nhận: {e}")
    
    return redirect("store_order_detail", order_id=order_id)


# ── ADMIN ORDER VIEWS ────────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_order_list(request):
    orders = []
    customers_map = {}
    try:
        r = requests.get(f"{ORDER_SERVICE_URL}/orders/", timeout=5)
        orders = r.json()
        if not isinstance(orders, list):
            orders = []
    except Exception:
        pass
    try:
        customers = requests.get(f"{CUSTOMER_SERVICE_URL}/customers/", timeout=3).json()
        if isinstance(customers, list):
            customers_map = {c["id"]: c for c in customers}
    except Exception:
        pass
    for order in orders:
        cust = customers_map.get(order.get("customer_id"), {})
        order["customer_name"] = cust.get("name", f"KH #{order.get('customer_id')}")
        order["customer_email"] = cust.get("email", "")
    return render(request, "orders.html", {"orders": orders})


@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_order_detail(request, order_id):
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status:
            try:
                requests.patch(f"{ORDER_SERVICE_URL}/orders/{order_id}/",
                               json={"status": new_status}, timeout=5)
                messages.success(request, f"Đã cập nhật trạng thái đơn hàng #{order_id}.")
            except Exception as e:
                messages.error(request, f"Lỗi: {e}")
        return redirect("admin_order_detail", order_id=order_id)

    order = None
    try:
        r = requests.get(f"{ORDER_SERVICE_URL}/orders/{order_id}/", timeout=5)
        if r.status_code == 200:
            order = r.json()
            # Customer info
            try:
                customers = requests.get(f"{CUSTOMER_SERVICE_URL}/customers/", timeout=3).json()
                cust = next((c for c in customers if c["id"] == order.get("customer_id")), {})
                order["customer_name"] = cust.get("name", f"KH #{order.get('customer_id')}")
                order["customer_email"] = cust.get("email", "")
            except Exception:
                order["customer_name"] = f"KH #{order.get('customer_id')}"
                order["customer_email"] = ""
            # Enrich items
            books_map = {}
            clothes_map = {}
            try:
                books = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=3).json()
                if isinstance(books, list):
                    books_map = {b["id"]: b for b in books}
            except Exception:
                pass
            try:
                clothes = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=3).json()
                if isinstance(clothes, list):
                    clothes_map = {c["id"]: c for c in clothes}
            except Exception:
                pass
            for item in order.get("items", []):
                actual_id = item.get("book_id")
                if isinstance(actual_id, int) and actual_id > 1000000:
                    clothe_id = actual_id - 1000000
                    clothe = clothes_map.get(clothe_id, {})
                    item["book_title"] = clothe.get("name", f"Quần áo #{clothe_id}")
                    item["book_author"] = clothe.get("material", "Thời trang")
                    item["image_url"] = f"https://loremflickr.com/100/140/fashion,clothes?lock={clothe_id}"
                else:
                    book = books_map.get(actual_id, {})
                    item["book_title"] = book.get("title", f"Sách #{actual_id}")
                    item["book_author"] = book.get("author", "")
                    item["image_url"] = f"https://loremflickr.com/100/140/book?lock={actual_id}"
    except Exception:
        pass
    return render(request, "order_detail.html", {"order": order})


# ── ADMIN STAFF VIEWS ─────────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_staff_list(request):
    error = None
    staff = []
    if request.method == "POST":
        data = {
            "name": request.POST.get("name"),
            "email": request.POST.get("email"),
            "phone": request.POST.get("phone", ""),
            "role": request.POST.get("role", "sales"),
        }
        try:
            r = requests.post(f"{STAFF_SERVICE_URL}/staff/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm nhân viên thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Không kết nối được staff-service: {e}")
        return redirect("admin_staff_list")
    try:
        r = requests.get(f"{STAFF_SERVICE_URL}/staff/", timeout=3)
        staff = r.json()
        if not isinstance(staff, list):
            staff = []
    except Exception as e:
        error = str(e)
    return render(request, "staff.html", {"staff": staff, "error": error})


# ── ADMIN MANAGER VIEWS ──────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_manager_list(request):
    error = None
    managers = []
    if request.method == "POST":
        data = {
            "name": request.POST.get("name"),
            "email": request.POST.get("email"),
            "phone": request.POST.get("phone", ""),
            "department": request.POST.get("department", "general"),
        }
        try:
            r = requests.post(f"{MANAGER_SERVICE_URL}/managers/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm quản lý thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Không kết nối được manager-service: {e}")
        return redirect("admin_manager_list")
    try:
        r = requests.get(f"{MANAGER_SERVICE_URL}/managers/", timeout=3)
        managers = r.json()
        if not isinstance(managers, list):
            managers = []
    except Exception as e:
        error = str(e)
    return render(request, "managers.html", {"managers": managers, "error": error})


# ── ADMIN CATALOG VIEWS ──────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_catalog_list(request):
    error = None
    categories = []
    if request.method == "POST":
        data = {
            "name": request.POST.get("name"),
            "description": request.POST.get("description", ""),
        }
        try:
            r = requests.post(f"{CATALOG_SERVICE_URL}/categories/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm danh mục thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Không kết nối được catalog-service: {e}")
        return redirect("admin_catalog_list")
    try:
        r = requests.get(f"{CATALOG_SERVICE_URL}/categories/", timeout=3)
        categories = r.json()
        if not isinstance(categories, list):
            categories = []
    except Exception as e:
        error = str(e)
    return render(request, "catalog.html", {"categories": categories, "error": error})


# ── ADMIN PAYMENT VIEWS ──────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_payment_list(request):
    payments = []
    try:
        r = requests.get(f"{PAY_SERVICE_URL}/payments/", timeout=5)
        payments = r.json()
        if not isinstance(payments, list):
            payments = []
    except Exception:
        pass
    return render(request, "payments.html", {"payments": payments})


# ── ADMIN SHIPMENT VIEWS ─────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_shipment_list(request):
    shipments = []
    try:
        r = requests.get(f"{SHIP_SERVICE_URL}/shipments/", timeout=5)
        shipments = r.json()
        if not isinstance(shipments, list):
            shipments = []
    except Exception:
        pass
    return render(request, "shipments.html", {"shipments": shipments})


# ── ADMIN REVIEW VIEWS ───────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_review_list(request):
    reviews = []
    try:
        r = requests.get(f"{COMMENT_RATE_SERVICE_URL}/reviews/", timeout=5)
        reviews = r.json()
        if not isinstance(reviews, list):
            reviews = []
    except Exception:
        pass
    return render(request, "reviews.html", {"reviews": reviews})


# ── STORE REVIEW VIEWS ───────────────────────────────────────

def store_add_review(request, book_id):
    customer = _get_store_customer(request)
    if not customer:
        messages.error(request, "Vui lòng đăng nhập để đánh giá.")
        return redirect("store_login")
    
    # Check if customer has bought this book and order is delivered
    has_purchased = False
    try:
        r_orders = requests.get(f"{ORDER_SERVICE_URL}/orders/customer/{customer['id']}/", timeout=5)
        if r_orders.status_code == 200:
            orders = r_orders.json()
            for order in orders:
                if order.get("status") == "delivered":
                    for item in order.get("items", []):
                        if item.get("book_id") == book_id:
                            has_purchased = True
                            break
                if has_purchased: break
    except Exception:
        pass
    
    if not has_purchased:
        messages.error(request, "Bạn chỉ có thể đánh giá sách sau khi đã nhận hàng thành công.")
        return redirect("store_book_detail", book_id=book_id)

    if request.method == "POST":
        data = {
            "customer_id": customer["id"],
            "book_id": book_id,
            "rating": int(request.POST.get("rating", 5)),
            "comment": request.POST.get("comment", ""),
        }
        try:
            r = requests.post(f"{COMMENT_RATE_SERVICE_URL}/reviews/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Đánh giá thành công!")
            else:
                resp = r.json()
                if "unique" in str(resp).lower() or "unique_together" in str(resp).lower():
                    messages.error(request, "Bạn đã đánh giá sách này rồi.")
                else:
                    messages.error(request, f"Lỗi: {resp}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối: {e}")
    return redirect("store_book_detail", book_id=book_id)


def api_secure_echo(request):
    return JsonResponse({
        "status": "ok",
        "message": "Gateway token validation passed",
    })


# ── CLOTHE VIEWS ─────────────────────────────────────────────

@user_passes_test(is_staff_check, login_url='/admin/login/')
def admin_clothe_list(request):
    error = None
    clothes = []
    if request.method == "POST":
        data = {
            "name": request.POST.get("name"),
            "material": request.POST.get("material"),
            "price": request.POST.get("price"),
            "stock": request.POST.get("stock"),
        }
        try:
            r = requests.post(f"{CLOTHE_SERVICE_URL}/clothes/", json=data, timeout=3)
            if r.status_code in (200, 201):
                messages.success(request, "Thêm quần áo thành công!")
            else:
                messages.error(request, f"Lỗi: {r.text}")
        except Exception as e:
            messages.error(request, f"Lỗi kết nối: {e}")
        return redirect("admin_clothe_list")
        
    try:
        r = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=3)
        clothes = r.json()
    except Exception as e:
        error = str(e)
    return render(request, "clothes.html", {"clothes": clothes, "error": error})

def store_clothes(request):
    clothes = []
    try:
        r = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=3)
        clothes = r.json()
    except Exception:
        pass

    customer = _get_store_customer(request)
    cart_count = _get_cart_count(customer["id"], request) if customer else 0
    return render(request, "store_clothes.html", {"clothes": clothes, "customer": customer, "cart_count": cart_count})

def store_clothe_detail(request, clothe_id):
    clothe = None
    try:
        r = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/{clothe_id}/", timeout=3)
        if r.status_code == 200:
            clothe = r.json()
    except Exception:
        pass
    customer = _get_store_customer(request)
    cart_count = _get_cart_count(customer["id"], request) if customer else 0
    return render(request, "store_clothe_detail.html", {"clothe": clothe, "customer": customer, "cart_count": cart_count})
