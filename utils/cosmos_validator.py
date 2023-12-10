class Validator:
    def __init__(self, pub_key, hex_key, key_assigned, voting_power, moniker):
        self.pub_key = pub_key
        self.hex_key = hex_key
        self.key_assigned = key_assigned
        self.voting_power = voting_power
        self.moniker = moniker
        self.soft_opt_out = False
        self.voting_power_percent = None
    
    def __str__(self):
        return f"{self.moniker:<30} | {self.pub_key} | {self.hex_key} | {self.key_assigned} | {self.voting_power} | {self.voting_power_percent} | {self.soft_opt_out}"