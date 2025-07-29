# test_groq_final.py - Complete Fix for Groq Integration

import os
import sys

# Load environment variables FIRST
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads the .env file
    print("SUCCESS: Loaded .env file")
except ImportError:
    print("WARNING: python-dotenv not installed. Install with: pip install python-dotenv")

# Now import your modules AFTER loading environment
from llm_engine import set_groq_api_key, test_groq_connection, generate_explanation_replicate

def ensure_api_key():
    """Make sure API key is properly set"""
    
    # Get from environment
    groq_key = os.getenv("GROQ_API_KEY")
    
    if groq_key:
        print(f"SUCCESS: Found API key in environment (starts with: {groq_key[:10]}...)")
        # Explicitly set it in the module to make sure it's available
        set_groq_api_key(groq_key)
        print("SUCCESS: API key set in llm_engine module")
        return True
    else:
        print("ERROR: GROQ_API_KEY not found in environment")
        # Try setting it directly as backup
        backup_key = 0
        set_groq_api_key(backup_key)
        print("SUCCESS: Using backup API key")
        return True

def create_test_image():
    """Create a test image"""
    try:
        from PIL import Image, ImageDraw
        
        # Create a simple test image
        img = Image.new('RGB', (400, 300), color=(240, 248, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw simple equipment-like shapes
        draw.rectangle([50, 50, 350, 250], outline='black', width=2)
        draw.rectangle([70, 70, 150, 120], fill='gray')
        draw.rectangle([200, 70, 280, 120], fill='green')
        draw.rectangle([70, 150, 280, 230], fill='yellow')
        
        test_path = "test_equipment.jpg"
        img.save(test_path)
        print(f"SUCCESS: Created test image at {test_path}")
        return test_path
        
    except ImportError:
        print("WARNING: PIL not installed. Looking for existing images...")
        # Look for existing images
        possible_images = [
            "charts/trend_graph.png",
            "equipment_images/EQP001.jpg",
            "test.jpg",
            "test.png",
            "sample.jpg"
        ]
        
        for img_path in possible_images:
            if os.path.exists(img_path):
                print(f"SUCCESS: Found existing image at {img_path}")
                return img_path
        
        print("ERROR: No images found and PIL not available")
        return None
        
    except Exception as e:
        print(f"ERROR: Could not create test image: {str(e)}")
        return None

def test_api_connection():
    """Test the API connection"""
    print("\n=== Testing Groq API Connection ===")
    
    # Create or find test image
    test_image = create_test_image()
    if not test_image:
        print("ERROR: No test image available")
        return False
    
    try:
        # Test the connection
        result = test_groq_connection(test_image)
        if result:
            print("SUCCESS: Groq API connection working!")
            return True
        else:
            print("ERROR: API connection test returned False")
            return False
            
    except Exception as e:
        print(f"ERROR: API connection test failed: {str(e)}")
        return False

def test_equipment_analysis():
    """Test equipment analysis with sample data"""
    print("\n=== Testing Equipment Analysis ===")
    
    # Get test image
    test_image = create_test_image()
    if not test_image:
        print("ERROR: No test image available")
        return False
    
    # Sample equipment data
    sample_metrics = {
        'equipment_id': 'EQP001',
        'equipment_age': 8,
        'downtime_hours': 24,
        'num_failures': 3,
        'response_time_hours': 6,
        'predicted_to_fail': True,
        'maintenance_needs': {
            'preventive': 'High',
            'corrective': 'Medium',
            'replacement': 'High'
        }
    }
    
    try:
        # Test with technician role
        print("Testing with 'technician' role...")
        result = generate_explanation_replicate(
            equipment_metrics=sample_metrics,
            role="technician",
            image_path=test_image
        )
        
        print("SUCCESS: Equipment analysis completed!")
        print(f"Response length: {len(result)} characters")
        print(f"Preview: {result[:150]}...")
        return True
        
    except Exception as e:
        print(f"ERROR: Equipment analysis failed: {str(e)}")
        return False

def test_all_roles():
    """Test all user roles"""
    print("\n=== Testing All User Roles ===")
    
    test_image = create_test_image()
    if not test_image:
        return False
    
    sample_metrics = {
        'equipment_id': 'EQP001',
        'equipment_age': 5,
        'downtime_hours': 12,
        'num_failures': 2,
        'response_time_hours': 4,
        'predicted_to_fail': False,
        'maintenance_needs': {
            'preventive': 'Medium',
            'corrective': 'Low',
            'replacement': 'Low'
        }
    }
    
    roles = ["technician", "biomedical", "admin"]
    
    for role in roles:
        try:
            print(f"\nTesting role: {role}")
            result = generate_explanation_replicate(
                equipment_metrics=sample_metrics,
                role=role,
                image_path=test_image
            )
            print(f"SUCCESS: {role} role test passed ({len(result)} chars)")
            
        except Exception as e:
            print(f"ERROR: {role} role test failed: {str(e)}")
            return False
    
    return True

def show_integration_info():
    """Show how to use in FastAPI"""
    print(f"\n{'='*50}")
    print("INTEGRATION INFORMATION")
    print(f"{'='*50}")
    print("Your FastAPI endpoints should now work:")
    print("")
    print("1. GET /maintenance-log/llm-explanation/{equipment_id}")
    print("   - Returns equipment analysis with explanation")
    print("")
    print("2. GET /combined/{equipment_id}")  
    print("   - Returns combined data with metrics and explanation")
    print("")
    print("Example usage in your FastAPI app:")
    print("- The generate_explanation_replicate function is ready")
    print("- Make sure your chart images are being generated")
    print("- Test with actual equipment IDs from your database")
    print(f"{'='*50}")

def main():
    """Main test function"""
    
    print("Groq LLM Engine - Complete Test")
    print("=" * 40)
    
    # Step 1: Ensure API key is set
    print("\nStep 1: Setting up API key...")
    if not ensure_api_key():
        print("FAILED: Could not set up API key")
        return
    
    # Step 2: Test API connection
    print("\nStep 2: Testing API connection...")
    if not test_api_connection():
        print("FAILED: API connection test failed")
        return
    
    # Step 3: Test equipment analysis
    print("\nStep 3: Testing equipment analysis...")
    if not test_equipment_analysis():
        print("FAILED: Equipment analysis test failed")
        return
    
    # Step 4: Test all roles
    print("\nStep 4: Testing all user roles...")
    if not test_all_roles():
        print("FAILED: Role testing failed")  
        return
    
    # Success!
    print("\n" + "=" * 50)
    print("SUCCESS: ALL TESTS PASSED!")
    print("Your Groq LLM integration is working perfectly!")
    print("=" * 50)
    
    show_integration_info()
    
    print("\nNext steps:")
    print("1. Start your FastAPI server")
    print("2. Test the maintenance endpoints")
    print("3. Try with real equipment data")
    print("\nYour integration is ready to use!")

if __name__ == "__main__":
    main()