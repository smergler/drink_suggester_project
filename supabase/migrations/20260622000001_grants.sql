-- Grant table privileges to authenticated users.
-- RLS policies restrict which rows each user can see/modify;
-- these GRANTs are the prerequisite that lets authenticated users
-- touch the tables at all (RLS alone is not enough).

GRANT SELECT, INSERT, UPDATE, DELETE ON public.bottles              TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.companions           TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.companion_preferences TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.sessions             TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.session_companions   TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.session_drinks       TO authenticated;

GRANT EXECUTE ON FUNCTION upsert_companion_like(uuid, text)    TO authenticated;
GRANT EXECUTE ON FUNCTION upsert_companion_dislike(uuid, text) TO authenticated;
