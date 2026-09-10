import os
import time
import json
import base64
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import matplotlib.pyplot as plt

def generate_report(result_json, image_path, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=20, textColor=colors.HexColor("#1A237E")))
    styles.add(ParagraphStyle(name='SectionHeader', parent=styles['Heading2'], fontSize=14, spaceBefore=15, spaceAfter=10, textColor=colors.HexColor("#283593")))
    styles.add(ParagraphStyle(name='NormalText', parent=styles['Normal'], fontSize=11, spaceAfter=10, leading=14))
    styles.add(ParagraphStyle(name='TraceText', parent=styles['Code'], fontSize=9, leading=12, backColor=colors.HexColor("#F5F5F5")))
    styles.add(ParagraphStyle(name='Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=1))

    story = []

    # 1. Header
    story.append(Paragraph("SatQuery AI — Remote Sensing Analysis Report", styles['CustomTitle']))
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    source = "GEE Live Fetch" if result_json.get("source") == "gee_live_fetch" else "User Upload"
    if result_json.get("fetch_date"):
        source += f" (Image Date: {result_json['fetch_date']})"
    if result_json.get("fetched_coordinates"):
        coords = result_json["fetched_coordinates"]
        source += f" | Lat: {coords['lat']:.4f}, Lon: {coords['lon']:.4f}"
        
    story.append(Paragraph(f"<b>Generated:</b> {timestamp}", styles['NormalText']))
    story.append(Paragraph(f"<b>Source:</b> {source}", styles['NormalText']))
    story.append(Spacer(1, 10))

    # 2. Query
    # Note: query is not stored in result_json right now. I should modify main.py to save 'query' in the result JSON.
    query = result_json.get("query", "N/A")
    story.append(Paragraph("<b>Query:</b>", styles['SectionHeader']))
    story.append(Paragraph(query, styles['NormalText']))
    
    # 3. Primary Image + Evidence Overlay
    story.append(Paragraph("<b>Visual Evidence:</b>", styles['SectionHeader']))
    
    # First the original image
    try:
        img = RLImage(image_path, width=400, height=300, kind='proportional')
        story.append(img)
        story.append(Spacer(1, 10))
    except Exception as e:
        print("Error embedding original image:", e)

    # Then overlay if present
    temp_files = []
    
    if result_json.get("heatmap_overlay_base64"):
        try:
            img_data = base64.b64decode(result_json["heatmap_overlay_base64"])
            buf = BytesIO(img_data)
            img = RLImage(buf, width=400, height=300, kind='proportional')
            story.append(Paragraph("Heatmap Overlay:", styles['NormalText']))
            story.append(img)
            story.append(Spacer(1, 10))
        except Exception:
            pass

    if result_json.get("forest_highlight_overlay_base64"):
        try:
            img_data = base64.b64decode(result_json["forest_highlight_overlay_base64"])
            buf = BytesIO(img_data)
            img = RLImage(buf, width=400, height=300, kind='proportional')
            story.append(Paragraph("Forest Cover Mask:", styles['NormalText']))
            story.append(img)
            story.append(Spacer(1, 10))
        except Exception:
            pass

    story.append(PageBreak())

    # 4. Answer
    story.append(Paragraph("<b>Analysis Result:</b>", styles['SectionHeader']))
    answer_text = result_json.get("answer", "").replace('\n', '<br/>')
    story.append(Paragraph(answer_text, styles['NormalText']))
    
    if result_json.get("confidence"):
        story.append(Paragraph(f"<b>Confidence:</b> {result_json['confidence'].title()}", styles['NormalText']))

    # 5. Supporting Analytics
    has_analytics = any([
        result_json.get("vegetation_breakdown"),
        result_json.get("forest_cover_trend"),
        result_json.get("flooded_area_pct") is not None
    ])
    
    if has_analytics:
        story.append(Paragraph("<b>Supporting Analytics:</b>", styles['SectionHeader']))
        
        if result_json.get("vegetation_breakdown"):
            try:
                data = result_json["vegetation_breakdown"]
                labels = [d["name"] for d in data]
                sizes = [d["value"] for d in data]
                colors_list = ['#e0e0e0', '#d4e157', '#66bb6a', '#2e7d32']
                
                plt.figure(figsize=(5, 4))
                plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors_list)
                plt.title("Vegetation Types")
                temp_pie = f"{output_path}_pie.png"
                plt.savefig(temp_pie, bbox_inches='tight')
                plt.close()
                temp_files.append(temp_pie)
                
                story.append(RLImage(temp_pie, width=300, height=240, kind='proportional'))
            except Exception as e:
                print("Error making pie chart:", e)
                
        if result_json.get("forest_cover_trend"):
            try:
                data = result_json["forest_cover_trend"]
                labels = [d["name"] for d in data]
                values = [d["value"] for d in data]
                
                plt.figure(figsize=(5, 4))
                plt.bar(labels, values, color='#4caf50')
                plt.ylim(0, 100)
                plt.ylabel("Forest Cover %")
                plt.title("Forest Cover Trend")
                temp_bar = f"{output_path}_bar.png"
                plt.savefig(temp_bar, bbox_inches='tight')
                plt.close()
                temp_files.append(temp_bar)
                
                story.append(RLImage(temp_bar, width=300, height=240, kind='proportional'))
            except Exception as e:
                print("Error making bar chart:", e)

        if result_json.get("flooded_area_pct") is not None:
            pct = result_json["flooded_area_pct"]
            story.append(Paragraph(f"<b>Flooded Area Detected:</b> {pct:.2f}% of the region.", styles['NormalText']))

    # 6. Execution Trace
    story.append(Paragraph("<b>Execution Trace:</b>", styles['SectionHeader']))
    trace = result_json.get("execution_trace", {})
    trace_str = (
        f"Task: {trace.get('task')}<br/>"
        f"Model Used: {trace.get('model_used')}<br/>"
        f"Provider: {trace.get('provider')}<br/>"
        f"Response Time: {trace.get('response_time_seconds')} seconds<br/>"
    )
    if trace.get('tool_called'):
        trace_str += f"Tool Called: {trace.get('tool_called')}<br/>"
    
    story.append(Paragraph(trace_str, styles['TraceText']))
    
    story.append(Spacer(1, 30))
    story.append(Paragraph("Generated automatically by SatQuery AI. For official verification, cross-check with authoritative sources.", styles['Footer']))

    doc.build(story)
    
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)

