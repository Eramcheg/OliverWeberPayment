import os
import json
import time
import logging
import tempfile
from datetime import datetime, timedelta
from subprocess import run
from io import BytesIO
import urllib.request
import ftplib
from django.views.generic import TemplateView
# Django imports
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponse, JsonResponse, FileResponse
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# Third-party imports
import stripe
import firebase_admin
from firebase_admin import credentials, firestore
from openpyxl import load_workbook
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
# from models import UserPayment


stripe.api_key = settings.STRIPE_SECRET_KEY
json_file_path = os.path.join(settings.BASE_DIR, "users", "static", "key5.json")

cred = credentials.Certificate(json_file_path)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

metadata_ref = db.collection('metadata')

keyValue = ""

def get_product_info(request, key):
    product_info = {}
    try:
        # Get a reference to the "Orders" collection
        collection_ref = db.collection("Orders")

        # Create a query to find documents where the "orderId" field matches the given key
        query = collection_ref.where("orderId", "==", key).limit(1)

        # Get the documents that match the query (at most one document should match)
        documents = query.stream()

        # Initialize product_info
        product_info = {}

        for doc in documents:
            # You can access the document reference using doc.reference
            document_ref = doc.reference

            # Retrieve data from the document
            doc_data = doc.to_dict()

            # Create the product_info dictionary
            product_info = {
                'name': doc_data.get('Status', ''),
                'description': doc_data.get('orderId', ''),
                'price': doc_data.get('price', ''),
                'orders': []  # Initialize an empty list for orders
            }
            # Retrieve the list of order references
            order_references = doc_data.get('list', [])
            # Iterate through the order references
            for order_ref in order_references:
                order_doc = order_ref.get()  # Get the referenced document
                order_data = order_doc.to_dict()  # Extract data from the referenced document
                order_info = {
                    'name': order_data.get('name', ''),
                    'quantity': order_data.get('quantity', 0)
                }
                product_info['orders'].append(order_info)  # Add order information to the list

            request.session['price'] = doc_data.get('price', '')
            request.session['Id'] = doc_data.get('orderId', '')
            request.session['orderId'] = "Order " + doc_data.get('orderId', '')
            # You found a matching document, break the loop
            break

    except Exception as e:
        # Handle any errors that may occur during Firebase interaction
        print("Error: ", e)
        product_info = {}

    return render(request, 'index.html', {'product_info': product_info})

def get_email_product_info(request, key):
    product_info = {}
    try:
        # Get a reference to the "Orders" collection
        collection_ref = db.collection("Orders")

        # Create a query to find documents where the "orderId" field matches the given key
        query = collection_ref.where("orderId", "==", key).limit(1)

        # Get the documents that match the query (at most one document should match)
        documents = query.stream()

        # Initialize product_info
        product_info = {}

        for doc in documents:
            # You can access the document reference using doc.reference
            document_ref = doc.reference

            # Retrieve data from the document
            doc_data = doc.to_dict()

            # Create the product_info dictionary
            product_info = {
                'name': doc_data.get('Status', ''),
                'description': doc_data.get('orderId', ''),
                'price': doc_data.get('price', ''),
                'orders': []  # Initialize an empty list for orders
            }
            # Retrieve the list of order references
            order_references = doc_data.get('list', [])
            # Iterate through the order references
            for order_ref in order_references:
                order_doc = order_ref.get()  # Get the referenced document
                order_data = order_doc.to_dict()  # Extract data from the referenced document
                order_info = {
                    'name': order_data.get('name', ''),
                    'quantity': order_data.get('quantity', 0)
                }
                product_info['orders'].append(order_info)  # Add order information to the list

            request.session['price'] = doc_data.get('price', '')
            request.session['Id'] = doc_data.get('orderId', '')
            request.session['orderId'] = "Order " + doc_data.get('orderId', '')
            # You found a matching document, break the loop
            break

    except Exception as e:
        # Handle any errors that may occur during Firebase interaction
        print("Error: ", e)
        product_info = {}

    return render(request, 'page_email.html', {'product_info': product_info})


def update_email(request):
    if request.method == 'POST':
        email = request.POST.get('customer-email')
        order_id = request.session.get('Id')  # Assuming 'Id' holds the orderId from previous function

        try:
            # Assuming 'db' is already defined and is a Firebase client instance
            collection_ref = db.collection("Orders")
            # Here, we are assuming 'orderId' is unique and directly accessible
            document_ref = collection_ref.document(order_id)

            # Update the 'email' field in the document
            document_ref.update({'Email': email})

            # Redirect to success.html after updating
            return render(request, 'success.html')
        except Exception as e:
            print("Error: ", e)
            # Handle error (maybe redirect to an error page or show a message)

    # If it's a GET request or any other method, render the original page with form
    return render(request, 'went_wrong.html')

def success(request):
    return render(request, 'success.html')

def payment(request):
    if request.method == 'POST':
        # Get the amount from the form (validate this)
        amount = int(request.session.get('price') * 100)

        # Create a payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
        )

        return render(request, 'payment.html', {'client_secret': intent.client_secret})

    return render(request, 'payment_form.html')
def payment_confirmation(request):
    return render(request, 'payment.html')

@csrf_exempt
def stripe_config(request):
    if request.method == 'GET':
        stripe_config = {'publicKey': settings.STRIPE_PUBLISHABLE_KEY}
        return JsonResponse(stripe_config, safe=False)


@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        domain_url = 'https://www.agentsoliverweber.com/'
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            # Parse the JSON object from the request body
            data = json.loads(request.body)

            # Get the email from the parsed JSON object
            email = data.get('email', None)
            code = data.get('code', None)
            phone = data.get('phone', None)
            name = data.get('name', None)
            surname = data.get('surname', None)
            print(email)
            print(code + phone)
            metadata = {'Id': request.session.get('Id'), "Email": email, "Phone": code + phone, "Name": name+" " + surname}


            # Create the checkout session with metadata
            checkout_session = stripe.checkout.Session.create(
                success_url=domain_url + 'success?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=domain_url + 'cancelled/',
                payment_method_types=['card'],
                mode='payment',
                line_items=[
                    {
                        'price_data': {
                            'currency': 'eur',
                            'product_data': {
                                'name': request.session.get('orderId'),
                            },
                            'unit_amount': int(request.session.get('price') * 100),
                        },
                        'quantity': 1,
                    }
                ],
                metadata=metadata,  # Include the previously defined metadata
            )
            return JsonResponse({'sessionId': checkout_session['id']})
        except Exception as e:
            return JsonResponse({'error': str(e)})

class SuccessView(TemplateView):
    template_name = 'success.html'
    def get(self, request):
        return render(request, self.template_name)

class CancelledView(TemplateView):
    template_name = 'cancelled.html'
    def get(self, request):
        return render(request, self.template_name)


@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    payload = request.body.decode('utf-8')
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        print("PAYLOAD")
        logging.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logging.error(f"Signature verification error: {e}")
        print("SIGNATURE")
        return HttpResponse(status=400)

    # Logging the event data
    logging.info(event)
    if event['type'] == 'checkout.session.completed':
        # Extract the session ID from the event data
        session_id = event['data']['object']['id']

        # Retrieve the metadata, including 'Id', from the session
        session = stripe.checkout.Session.retrieve(session_id)
        metadata = session.metadata

        # Access 'Id' from metadata and update Firestore
        order_id = metadata.get('Id')
        if order_id:
            collection_ref = db.collection("Orders")
            doc_ref = collection_ref.document(order_id)

            # Update the 'Status' field to 'Paid'

            user_email = metadata.get('Email')
            user_phone = metadata.get("Phone")
            user_name = metadata.get("Name")
            if user_email:
                print(user_email)
                doc_ref.update({"Email": user_email})
            if user_phone:
                doc_ref.update({"Phone": user_phone})
            if user_name:
                doc_ref.update({"Name": user_name})
            doc_ref.update({"Status": "Paid"})
            print(f"Order {order_id} has been marked as paid.")

    return HttpResponse(status=200)

def some_view(request, key):
    # Sample dynamic data

    collection_ref = db.collection("Orders")
    query = collection_ref.where("orderId", "==", key).limit(1)

    documents = query.stream()

    product_info = {}
    for doc in documents:
        # Retrieve data from the document
        doc_data = doc.to_dict()

        # Create the product_info dictionary
        product_info = {
            'Name': doc_data.get('Name', ''),
            'Email': doc_data.get('Email', ''),
            'Phone': doc_data.get('Phone', ''),
            'Date': doc_data.get('date', ''),
            'price':doc_data.get('price', ''),
            'Status':doc_data.get('Status', ''),
            'orders':[],
            'checkid': doc_data.get('checkId', ''),
            'Id':doc_data.get('orderId', ''),
        }

        # You found a matching document, break the loop
        break
    if product_info.get('Status') != 'Paid':
        return render(request, 'non_exist.html')

    order_references = product_info.get('list', [])
                # Iterate through the order references
    for order_ref in order_references:
        order_doc = order_ref.get()  # Get the referenced document
        order_data = order_doc.to_dict()  # Extract data from the referenced document
        order_info = {
            'name': order_data.get('number', ''),
            'quantity': order_data.get('quantity', 0),
            'price': "{:.2f}".format(order_data.get('price', 0)),
            'vat':"22%",
            'totale': "{:.2f}".format(order_data.get('price', 0) * order_data.get('quantity', 0))
        }
        product_info['orders'].append(order_info)  # Add order information to the list

    client_name = product_info['Name']
    phone_or_email = product_info['Email']
    if len(product_info["Phone"]) <= 5:
        phone_or_email = product_info['Email']
    else:
        phone_or_email = product_info["Phone"]
    print(product_info['Date'])
    date = product_info['Date']
    date = str(date)
# Handle the UTC offset format
  #  date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f%z")
 #   date = date.strftime("%d.%m.%Y %H:%M")
#    date = str(date)

    price = product_info['price']
    checkId = product_info['checkId']

    vat = round(price - price/1.22, 2)
    price = "{:.2f}".format(price)
    query = collection_ref.where('Status', '==', 'Paid')
    documents = query.stream()
        # Count the number of documents that match the query
    count = 0
    for i in documents:
            count+=1
    products = []
    for order in product_info['orders']:
        product_entry = [
            order['name'],
            str(order['quantity']),
            "€" + order['price'],
            order['vat'],
            "€" + order['totale']
        ]
        products.append(product_entry)

    # Create the HttpResponse object with the appropriate PDF headers.
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f"attachment; filename=receipt_{product_info['Id']}"

    buffer = BytesIO()

        # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=24, alignment=1, spaceAfter=0.2*inch)
    center_bold_style = ParagraphStyle('CenterBold', parent=styles['Normal'], fontSize=12, alignment=1, fontName='Times-Bold')
    bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontSize=12, fontName='Times-Bold')

        # Set up document
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20, topMargin=20)
    content = []

        # Translate LaTeX content to ReportLab elements
    content.append(Paragraph("OLIVER WEBER ITALY S.R.L.", title_style))
    content.append(Paragraph("BOLZANO (BZ)", center_bold_style))
    content.append(Paragraph("VIA DEI CAPPUCCINI 8 CAP 39100", center_bold_style))
    content.append(Paragraph("P.IVA 03223020219", center_bold_style))
    content.append(Paragraph("DOCUMENTO COMMERCIALE", center_bold_style))
    content.append(Paragraph("di vendita online", center_bold_style))
    content.append(Spacer(1, 0.3*inch))
    content.append(Paragraph(f"Nome del cliente: {client_name}", bold_style))

        # Table with products
    table_data = [["Prodotto", "Quantità", "Prezzo unitario", "IVA", "Totale"]]
    table_data.extend(products)

        # Adjusted column widths
    table = Table(table_data, colWidths=[1.7 * inch, 1.0 * inch, 1.7 * inch, 1.0 * inch, 1.3 * inch])

    table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), '#f0f0f0'),
            ('TEXTCOLOR', (0, 0), (-1, 0), '#000000'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), '#ffffff'),
            ('GRID', (0, 0), (-1, -1), 1, '#000000')
        ])
    table.setStyle(table_style)
    content.append(Spacer(1, 1 * cm))

        # Append the table after the spacer
    content.append(table)

    content.append(Spacer(1, 0.5*inch))
    content.append(Paragraph(f"Totale complessivo: €{price}", bold_style))
    content.append(Paragraph(f"di cui IVA: €{vat}", bold_style))
    content.append(Spacer(1, 0.3*inch))
    content.append(Paragraph(f"Pagamento Stripe: €{price}", center_bold_style))
    content.append(Paragraph(f"Data: {date}                                 Numero di telefono o e-mail: {phone_or_email}", center_bold_style))
    content.append(Spacer(1, 0.*inch))
    content.append(Paragraph(f"DOCUMENTO N.: {checkId}", center_bold_style))
    content.append(Paragraph("Grazie per il tuo acquisto!", center_bold_style))

    doc.build(content)

        # Get the value of the BytesIO buffer and write it to the response.
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response

def get_check_id():
    @firestore.transactional
    def increment_check_id(transaction, check_counter_ref):
        snapshot = check_counter_ref.get(transaction=transaction)
        last_check_id = snapshot.get('lastCheck') if snapshot.exists else 10000
        new_check_id = last_check_id + 1
        transaction.update(check_counter_ref, {'lastCheck': new_check_id})
        return new_check_id

    check_counter_ref = metadata_ref.document('checkCounter')
    transaction = db.transaction()
    new_check_id = increment_check_id(transaction, check_counter_ref)
    return new_check_id