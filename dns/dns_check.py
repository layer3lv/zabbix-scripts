import sys
import dns.resolver
import whois
from datetime import datetime

def get_txt_record(domain):
    try:
        resolvers = ['1.1.1.1', '9.9.9.9']
        for resolver_ip in resolvers:
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = [resolver_ip]
            response = resolver.resolve(domain, 'TXT')

            for rrset in response:
                for txt_string in rrset.strings:
                    txt_record = txt_string.decode("utf-8")
                    if "v=expire date=" in txt_record:
                        return txt_record
        return None
    except dns.resolver.NXDOMAIN:
        return None
    except dns.resolver.NoAnswer:
        return None
    except dns.exception.DNSException:
        return None

def get_whois_expiration_date(domain):
    try:
        w = whois.whois(domain)
        expiration_date = w.expiration_date
        if isinstance(expiration_date, list):
            expiration_date = expiration_date[0]
        return expiration_date
    except whois.parser.PywhoisError:
        return None

def calculate_days_left(expire_date_str):
    try:
        expire_date = datetime.strptime(expire_date_str, "%Y-%m-%d")
        current_date = datetime.today()
        days_left = (expire_date - current_date).days
        return days_left
    except ValueError:
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script_name.py domain1 domain2 domain3 ...")
        sys.exit(1)

    domains = sys.argv[1:]

    for domain_name in domains:
        txt_record = get_txt_record(domain_name)
        if txt_record:
            expire_date_str = txt_record.split("v=expire date=")[1].strip()
        else:
            whois_expiration_date = get_whois_expiration_date(domain_name)
            if whois_expiration_date:
                expire_date_str = whois_expiration_date.strftime("%Y-%m-%d")
            else:
                print(f"No TXT record or WHOIS info found for domain '{domain_name}'.")
                continue

        days_left = calculate_days_left(expire_date_str)
        if days_left is not None:
            print(days_left)
        else:
            print(f"Error calculating days left for domain '{domain_name}'.")
