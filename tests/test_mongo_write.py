# """Test script to write data to local MongoDB"""
# from engine.mongodb_helper import MongoDBHelper

# # Test data
# rally_theme = "TEST-123"
# metadata = {
#     'idea': 'test-idea-001',
#     'name': 'Test Project Plan',
#     'tag': 'TestTag',
#     'prj': 'PRJ-001',
#     'go live': '2025-12-01',
#     'bdl': '2025-11-25',
#     'rdl': '2025-11-28'
# }

# try:
#     # Connect and save
#     print("Connecting to MongoDB...")
#     mongo_helper = MongoDBHelper()
    
#     print(f"Saving metadata for theme: {rally_theme}")
#     mongo_helper.save_plan_metadata(rally_theme, metadata)
    
#     print("✓ Successfully saved to MongoDB!")
    
#     # Read it back to verify
#     print("\nReading back from MongoDB...")
#     result = mongo_helper.get_plan_metadata(rally_theme)
#     print(f"Retrieved data: {result}")
    
#     mongo_helper.close()
#     print("\n✓ Test complete!")
    
# except Exception as e:
#     print(f"✗ Error: {e}")
#     import traceback
#     traceback.print_exc()
