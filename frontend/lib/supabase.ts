import { createClient } from "@supabase/supabase-js";

// Grab the URL and Key from the .env file
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

// This creates the bridge we will use in our login/signup pages
export const supabase = createClient(supabaseUrl, supabaseAnonKey)