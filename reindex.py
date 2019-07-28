from dgm_bot.dgmparse import session, Show, add_to_index

for show in session.query(Show).all():
    add_to_index('dgm_shows', show)
