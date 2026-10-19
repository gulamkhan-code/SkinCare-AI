
from flask import Flask, render_template, request, url_for, jsonify
import uuid
import os
import csv
import cv2

from skin_analysis import analyze_skin
from recommendation import get_recommendations, get_routine, get_catalog_recommendations

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
PRODUCT_FOLDER = "static/products"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PRODUCT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Temporary storage for recommendation pages during the local demo.
RESULT_CACHE = {}


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- AI ANALYSIS ----------------

@app.route("/analysis", methods=["GET", "POST"])
def analysis():
    if request.method == "POST":
        name = request.form.get("name")
        age = request.form.get("age")
        preference = request.form.get("preference")
        image = request.files.get("face_image")

        if image and image.filename:
            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                image.filename
            )

            image.save(image_path)
            img = cv2.imread(image_path)

            if img is not None:
                height, width, _ = img.shape
                analysis_result = analyze_skin(image_path)
                analysis_result["image_size"] = f"{width} × {height}"

                # Get recommendations from the product catalog.
                recommendations = get_catalog_recommendations(
                    analysis_result["skin_type"],
                    analysis_result["concerns"]
                )

                # Locate recommended product images.
                product_folder = os.path.join(
                    app.static_folder,
                    "products"
                )

                for product in recommendations:
                    image_name = (
                        product.get("image") or ""
                    ).strip()

                    product["image_url"] = ""

                    if image_name:
                        for root, _folders, files in os.walk(product_folder):
                            matched_file = next(
                                (
                                    filename for filename in files
                                    if filename.lower() == image_name.lower()
                                ),
                                None
                            )

                            if matched_file:
                                full_path = os.path.join(
                                    root,
                                    matched_file
                                )

                                relative_path = os.path.relpath(
                                    full_path,
                                    app.static_folder
                                )

                                product["image_url"] = url_for(
                                    "static",
                                    filename=relative_path.replace("\\", "/")
                                )
                                break

                # Preserve morning and night skincare routines.
                routine = get_routine(
                    analysis_result["skin_type"]
                )

                result_context = {
                    "name": name,
                    "age": age,
                    "preference": preference,
                    "image_path": "/" + image_path.replace("\\", "/"),
                    "result": analysis_result,
                    "recommendations": recommendations,
                    "routine": routine,
                }

                # Scanner UI uses fetch(), so return a real results URL.
                if request.headers.get("X-Requested-With") == "fetch":
                    # Keep the temporary cache bounded for the local demo.
                    if len(RESULT_CACHE) >= 50:
                        RESULT_CACHE.pop(next(iter(RESULT_CACHE)))

                    token = uuid.uuid4().hex
                    RESULT_CACHE[token] = result_context

                    return jsonify({
                        "redirect_url": url_for(
                            "analysis_result",
                            token=token
                        )
                    })

                # Normal HTML form submission fallback.
                return render_template(
                    "result.html",
                    **result_context
                )

    return render_template("analysis.html")


# ---------------- RECOMMENDATION RESULTS ----------------

@app.route("/recommendations/<token>")
def analysis_result(token):
    result_context = RESULT_CACHE.get(token)

    if result_context is None:
        return (
            "These recommendations have expired. "
            "Please run the skin analysis again.",
            404
        )

    return render_template(
        "result.html",
        **result_context
    )


# ---------------- PROGRESS ----------------

@app.route("/progress", methods=["GET", "POST"])
def progress():
    if request.method == "POST":
        before_image = request.files.get("before_image")
        after_image = request.files.get("after_image")

        if before_image and after_image:
            before_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                "before_" + before_image.filename
            )

            after_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                "after_" + after_image.filename
            )

            before_image.save(before_path)
            after_image.save(after_path)

            before_result = analyze_skin(before_path)
            after_result = analyze_skin(after_path)

            improved = [
                concern for concern in before_result["concerns"]
                if concern not in after_result["concerns"]
            ]

            new_concerns = [
                concern for concern in after_result["concerns"]
                if concern not in before_result["concerns"]
            ]

            return render_template(
                "progress_result.html",
                before_image="/" + before_path.replace("\\", "/"),
                after_image="/" + after_path.replace("\\", "/"),
                before_result=before_result,
                after_result=after_result,
                improved=improved,
                new_concerns=new_concerns
            )

    return render_template("progress.html")


# ---------------- BEAUTY SHOP ----------------

@app.route("/shop")
def shop():
    products = []

    with open(
        "products.csv",
        newline="",
        encoding="utf-8"
    ) as file:
        reader = csv.DictReader(file, delimiter="\t")

        for product in reader:
            image_name = (
                product.get("image") or ""
            ).strip()

            product["image_url"] = ""

            # Search all folders inside static/products.
            if image_name:
                for root, _folders, files in os.walk(PRODUCT_FOLDER):
                    matched_file = next(
                        (
                            filename for filename in files
                            if filename.lower() == image_name.lower()
                        ),
                        None
                    )

                    if matched_file:
                        full_path = os.path.join(root, matched_file)

                        relative_path = os.path.relpath(
                            full_path,
                            app.static_folder
                        )

                        product["image_url"] = url_for(
                            "static",
                            filename=relative_path.replace("\\", "/")
                        )
                        break

            products.append(product)

    collections = sorted({
        product.get("collection", "")
        for product in products
        if product.get("collection", "")
    })

    categories = sorted({
        product.get("category", "")
        for product in products
        if product.get("category", "")
    })

    return render_template(
        "shop.html",
        products=products,
        collections=collections,
        categories=categories
    )


# ---------------- PRODUCT DETAIL ----------------

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = None

    with open(
        "products.csv",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        reader = csv.DictReader(file, delimiter="\t")

        for row in reader:
            if (row.get("id") or "").strip() == str(product_id):
                product = row
                break

    if product is None:
        return "Product not found", 404

    image_name = (product.get("image") or "").strip()
    product["image_url"] = ""

    if image_name:
        product_folder = os.path.join(
            app.static_folder,
            "products"
        )

        for root, _folders, files in os.walk(product_folder):
            matched_file = next(
                (
                    filename for filename in files
                    if filename.lower() == image_name.lower()
                ),
                None
            )

            if matched_file:
                full_path = os.path.join(root, matched_file)

                relative_path = os.path.relpath(
                    full_path,
                    app.static_folder
                )

                product["image_url"] = url_for(
                    "static",
                    filename=relative_path.replace("\\", "/")
                )
                break

    return render_template(
        "product.html",
        product=product
    )


# ---------------- CART ----------------

@app.route("/cart")
def cart():
    return render_template("cart.html")


# ---------------- CHECKOUT ----------------

@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


# ---------------- RUN APP ----------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
