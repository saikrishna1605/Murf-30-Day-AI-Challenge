import asyncio
import requests
import json

async def test_error_readout():
    """Test the error readout functionality"""
    
    print("🎤 Testing Error Readout System")
    print("=" * 50)
    
    # Test 1: Generate error audio endpoint
    print("\n1. Testing Error Audio Generation:")
    try:
        response = requests.post(
            'http://localhost:8000/generate-error-audio',
            json={
                'message': 'This is a test error message for audio generation'
            },
            timeout=30
        )
        
        data = response.json()
        print(f"   Status: {data['status']}")
        if data.get('audio_url'):
            print(f"   Audio URL: {data['audio_url'][:50]}...")
        else:
            print(f"   Message: {data.get('message', 'No message')}")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Test TTS with empty text (should trigger error)
    print("\n2. Testing Empty Text Error:")
    try:
        response = requests.post(
            'http://localhost:8000/generate-audio',
            json={
                'text': '',
                'voice_id': 'en-US-natalie'
            },
            timeout=10
        )
        
        print(f"   Status Code: {response.status_code}")
        data = response.json()
        
        if 'detail' in data:
            if isinstance(data['detail'], dict) and 'fallback' in data['detail']:
                print(f"   Fallback Message: {data['detail']['fallback']}")
            else:
                print(f"   Error Detail: {data['detail']}")
                
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Test health endpoint
    print("\n3. Testing Health Check:")
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        data = response.json()
        print(f"   Overall Status: {data['status']}")
        print(f"   Services:")
        for service, status in data['services'].items():
            print(f"     - {service}: {status}")
            
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n✅ Error readout testing completed!")
    print("\n📝 How to test in the browser:")
    print("   1. Open http://localhost:8000")
    print("   2. Toggle the '🔊 Read error messages aloud' setting")
    print("   3. Try recording without microphone permission")
    print("   4. Try submitting empty text in TTS form")
    print("   5. Listen for error messages being read aloud")

if __name__ == "__main__":
    asyncio.run(test_error_readout())
