import json
import asyncio
from .constants import Constants

class MQTTCallback:
    def __init__(self, device=None, commands=None):
        self.device = device
        self.commands = commands
        self.logger = self.commands.logger # Hacky - but ... does it work? Passing logger to the class, will create duplicate log lines
    
    async def delegate(self, client, userdata, message):
        # Decode and convert the JSON string to a dictionary
        payload = json.loads(message.payload.decode("utf-8"))
        
        # Get the key of the payload
        key = next(iter(payload))
                
        # Retrieve the function from functions, based on the key retrieved
        value = payload[key]
        
        if key == "charge_state" and value:
            amps = int(self.device.config['charge_amps'])
            self.logger.info(f"Starting charge with amps to {amps}.")
            await self.commands.set_charge_start(amps)
        
        if key == "charge_state" and not value:
            self.logger.info(f"Stopping charge.")
            await self.commands.set_charge_stop()
            
        if key == "charge_amps":
            self.logger.info(f"Setting charge amps to {value}.")
            self.device.config = payload
            await self.commands.set_config_output_amps(value)

            # If the wallbox is actively charging, set_config_output_amps alone does not
            # affect the running session (the amps were baked into set_charge_start).
            # Stop and restart with the new value so the change takes effect immediately.
            if self.device.charge.get('output_state') == "Charging":
                self.logger.info(f"Charging active — restarting session with {value} A.")
                await self.commands.set_charge_stop()

                # Wait until the wallbox is truly ready for a new session (max 20 s, poll every 500 ms).
                # After set_charge_stop the wallbox briefly enters a transient state where
                # output_state is already "Idle" but current_state is "Unknown 7" / "Finished".
                # Only once current_state returns to "Charging" (CP-line state C: EV actively
                # requesting charge) is the wallbox ready to accept set_charge_start again.
                for _ in range(40):
                    await asyncio.sleep(0.5)
                    output_state = self.device.charge.get('output_state')
                    current_state = self.device.charge.get('current_state')
                    self.logger.debug(f"Waiting for ready state — output_state: {output_state}, current_state: {current_state}")
                    if output_state == "Idle" and current_state == "Charging":
                        self.logger.info(f"Wallbox ready (Idle + CP active) — sending charge_start with {value} A.")
                        break
                else:
                    self.logger.warning(f"Wallbox did not reach ready state after 20 s — output: {self.device.charge.get('output_state')}, current: {self.device.charge.get('current_state')} — skipping restart.")
                    return

                await asyncio.sleep(1)
                await self.commands.set_charge_start(int(value))

            # Re-issue get_config_output_amps to retrieve the data and put in device.config
            await self.commands.get_config_output_amps()
            
        if key == "lcd_brightness":
            self.logger.info(f"Setting LCD brightness to {value}.")
            await self.commands.set_config_lcd_brightness(value)
            
        if key == "temperature_unit":
            unit = Constants.TEMPERATURE_UNIT[value]
            self.logger.info(f"Setting Temperature Unit to {value} ({unit}).")
            await self.commands.set_config_temperature_unit(unit)
            
        if key == "language":
            language = Constants.LANGUAGES[value]
            self.logger.info(f"Setting Language to {value} ({language}).")
            await self.commands.set_config_language(language)
            
        if key == "device_name":
            self.logger.info(f"Setting name to {value}.")
            await self.commands.set_config_name(value)
            
            # Re-issue get_config_name to retrieve the data and put in device.config
            await self.commands.get_config_name()