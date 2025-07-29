# backend/llm_engine.py - Updated to use Groq API
import requests
import base64
import os
from fastapi import HTTPException

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Groq API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def generate_llm_explanation(equipment_metrics: dict, role: str, image_path: str = "") -> str:
    """
    Generate equipment health explanation using Groq Vision API
    (Function name kept as 'ollama' for compatibility with existing routes)
    """
    role = role.lower()
    tone = {
        "technician": "Provide a clear and actionable summary using non-technical language.",
        "biomedical": "Provide detailed analysis with technical insights, patterns, and preventive actions.",
        "admin": "Give a summarized overview with justification and potential resource implications."
    }.get(role, "Explain in general terms.")

    prompt = f"""
You are an AI assistant monitoring hospital equipment health with expertise in data visualization analysis.

Role: {role.capitalize()}
Tone: {tone}

Equipment Summary:
- Equipment ID: {equipment_metrics['equipment_id']}
- Age: {equipment_metrics['equipment_age']} years
- Downtime: {equipment_metrics['downtime_hours']} hours
- Failures: {equipment_metrics['num_failures']}
- Avg Response Time: {equipment_metrics['response_time_hours']} hrs
- Predicted to Fail: {"Yes" if equipment_metrics['predicted_to_fail'] else "No"}
- Maintenance Priorities:
    - Preventive: {equipment_metrics['maintenance_needs']['preventive']}
    - Corrective: {equipment_metrics['maintenance_needs']['corrective']}
    - Replacement: {equipment_metrics['maintenance_needs']['replacement']}

INSTRUCTIONS:
1. First, analyze the PROVIDED GRAPH/CHART IMAGE carefully and describe what trends, patterns, or data visualizations you observe.
2. Then explain the equipment's health based on the metrics provided above.
3. Correlate the visual data from the graph with the numerical metrics where possible.
4. Format your response in clean, readable text WITHOUT markdown symbols (**, *, etc.).
5. Use clear bullet points with simple dashes (-) and proper line breaks.
6. Structure your response as follows:

GRAPH ANALYSIS:
[Describe what you see in the graph/chart - trends, patterns, time periods, data points, etc.]

EQUIPMENT HEALTH ASSESSMENT:
[Your analysis based on the metrics]

ACTIONABLE RECOMMENDATIONS:
[Specific steps based on both graph trends and metrics]

Provide a comprehensive analysis that combines both visual data interpretation and metric-based assessment.
"""

    try:
        # Prepare headers for Groq API
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Prepare message content
        message_content = [{"type": "text", "text": prompt}]
        
        # Add image if provided
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img_file:
                base64_image = base64.b64encode(img_file.read()).decode()
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
        
        # Prepare payload for Groq API
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": message_content
                }
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
            "top_p": 1,
            "stream": False
        }
        
        # Make API call to Groq
        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )
        
        response.raise_for_status()
        
        # Extract response content
        result = response.json()
        explanation = result["choices"][0]["message"]["content"]
        
        return explanation if explanation else "No explanation returned."
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Groq API error: {str(e)}")
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Groq response format error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq error: {str(e)}")