from rent_management.subscription import start_trial


def execute():
	# sites that existed before subscriptions get the same free trial as new sites
	start_trial()
