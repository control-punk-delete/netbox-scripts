from extras.scripts import Script
class MyCustomScript(Script):
    def run(self, data, commit):
        username = self.request.user.username
        ip_address = self.request.META.get('HTTP_X_FORWARDED_FOR') or self.request.META.get('REMOTE_ADDR') 
        self.log_info(f"Running as user {username} (IP: {ip_address})...")

class AnotherCustomScript(Script):
    def run(self, data, commit):

        self.log_info(f"Finish")



script_order = (MyCustomScript, AnotherCustomScript)