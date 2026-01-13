import pandas as pd
from io import BytesIO, StringIO
from flask import Response
from bson import ObjectId

def export_to_excel(registrations):
    """Export registrations to Excel format"""
    # Convert to DataFrame
    data = []
    for reg in registrations:
        data.append({
            'ID': str(reg.get('_id', '')),
            'Full Name': reg.get('full_name', ''),
            'Email': reg.get('email', ''),
            'Institution': reg.get('institution', ''),
            'Segment': reg.get('segment_name', ''),
            'Category': reg.get('category', ''),
            'CA Ref': reg.get('ca_ref', ''),
            'Bkash Number': reg.get('bkash_number', ''),
            'Transaction ID': reg.get('transaction_id', ''),
            'Verified': 'Yes' if reg.get('verified') else 'No',
            'Registration Date': reg.get('registration_date', ''),
            'Verified At': reg.get('verified_at', '')
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Registrations', index=False)
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment;filename=registrations.xlsx'}
    )

def export_to_csv(registrations):
    """Export registrations to CSV format"""
    # Convert to DataFrame
    data = []
    for reg in registrations:
        data.append({
            'ID': str(reg.get('_id', '')),
            'Full Name': reg.get('full_name', ''),
            'Email': reg.get('email', ''),
            'Institution': reg.get('institution', ''),
            'Segment': reg.get('segment_name', ''),
            'Category': reg.get('category', ''),
            'CA Ref': reg.get('ca_ref', ''),
            'Bkash Number': reg.get('bkash_number', ''),
            'Transaction ID': reg.get('transaction_id', ''),
            'Verified': 'Yes' if reg.get('verified') else 'No',
            'Registration Date': reg.get('registration_date', ''),
            'Verified At': reg.get('verified_at', '')
        })
    
    df = pd.DataFrame(data)
    
    # Create CSV file in memory
    output = StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=registrations.csv'}
    )