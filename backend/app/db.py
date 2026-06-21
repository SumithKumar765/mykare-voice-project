from supabase import create_client, Client
from datetime import datetime
from app.config import settings

# Initialize the Supabase client using your secure settings
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

async def identify_user_db(phone_number: str, name: str = None):
    """Finds an existing user by phone number or creates a new one."""
    # Normalize phone number (strip everything except digits)
    normalized_phone = "".join(filter(str.isdigit, phone_number))
    
    # 1. Search for the existing user in Supabase
    res = supabase.table("users").select("*").eq("phone_number", normalized_phone).execute()

    # 2. IF THE USER EXISTS:
    if res.data and len(res.data) > 0:
        existing_user = res.data[0]
        
        # Auto-Correction: If the database name is "unknown" but the AI just captured their real name, update it!
        if name and existing_user.get("name") in ["unknown", "Unknown", None]:
            update_resp = supabase.table('users').update({"name": name}).eq('id', existing_user["id"]).execute()
            existing_user = update_resp.data[0]

        return {
            "user_id": existing_user["id"],
            "name": existing_user["name"],
            "is_new_user": False,
            "status": "Found existing user"
        }
        
    # 3. IF THE USER DOES NOT EXIST:
    else:
        # The Gatekeeper: If the AI hasn't captured a name yet, force it to ask the user
        if not name:
            return {
                "error": "User not found. You must ask the caller for their full name to register them."
            }

        # The Creation: If the AI has the name, insert the brand new user into Supabase!
        new_user_data = {
            "phone_number": normalized_phone,
            "name": name
        }
        insert_response = supabase.table('users').insert(new_user_data).execute()
        new_user = insert_response.data[0]

        return {
            "user_id": new_user["id"],
            "name": new_user["name"],
            "is_new_user": True,
            "status": "Created new user"
        }

async def fetch_slots_db(date_str: str = None):
    """Returns mock available slots, filtering out ones already booked in the DB."""
    target_date = date_str or datetime.utcnow().date().isoformat()
    
    # Hardcoded base availability (Mock data per your PRD)
    all_slots = ["09:00:00", "10:00:00", "11:00:00", "14:00:00", "15:00:00", "16:00:00"]
    
    # Fetch already booked slots for this date
    booked_res = supabase.table("appointments").select("time").eq("date", target_date).eq("status", "confirmed").execute()
    booked_times = [item["time"] for item in booked_res.data]
    
    # Filter out booked slots
    available = [{"time": t, "date": target_date} for t in all_slots if t not in booked_times]
    return {"slots": available[:5]} # Return max 5 slots so the AI doesn't read a massive list

async def book_appointment_db(user_id: str, date: str, time: str):
    """Books an appointment. Relies on Supabase UNIQUE index to block double-bookings."""
    try:
        data = {"user_id": user_id, "date": date, "time": time, "status": "confirmed"}
        res = supabase.table("appointments").insert(data).execute()
        return {"appointment_id": res.data[0]["id"], "status": "confirmed", "date": date, "time": time}
    except Exception as e:
        # If the unique constraint fails, it means someone else took the slot
        return {"appointment_id": None, "status": "conflict", "date": date, "time": time}

async def retrieve_appointments_db(user_id: str, status_filter: str = "confirmed"):
    """Fetches a user's upcoming appointments."""
    res = supabase.table("appointments").select("*").eq("user_id", user_id).eq("status", status_filter).execute()
    return {"appointments": res.data}

async def cancel_appointment_db(appointment_id: str):
    """Soft deletes an appointment by changing its status."""
    res = supabase.table("appointments").update({"status": "cancelled"}).eq("id", appointment_id).execute()
    if res.data:
        return {"status": "cancelled"}
    return {"status": "not_found"}

async def modify_appointment_db(appointment_id: str, new_date: str, new_time: str):
    """Changes the time of an appointment safely."""
    # Step 1: Check if new slot is taken
    check_conflict = supabase.table("appointments").select("*").eq("date", new_date).eq("time", new_time).eq("status", "confirmed").execute()
    if check_conflict.data:
        return {"status": "conflict"}
        
    # Step 2: Update if free
    res = supabase.table("appointments").update({"date": new_date, "time": new_time}).eq("id", appointment_id).execute()
    if res.data:
        return {"status": "modified"}
    return {"status": "not_found"}