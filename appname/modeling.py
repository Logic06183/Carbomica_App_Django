from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

class GreenInvestmentAnalyzer:
    def __init__(self):
        # Constants for calculations
        self.CARBON_CREDIT_PRICE = Decimal('15.00')  # USD per ton of CO2
        self.ELECTRICITY_COST = Decimal('0.15')  # USD per kWh
        self.INFLATION_RATE = Decimal('0.03')  # 3% annual inflation
        self.DISCOUNT_RATE = Decimal('0.05')  # 5% discount rate for NPV calculations
        
        # Intervention effectiveness rates
        self.EFFECTIVENESS = {
            'SOLAR': {
                'grid_electricity': Decimal('0.70'),  # 70% reduction in grid electricity
                'maintenance_savings': Decimal('0.10'),  # 10% reduction in maintenance costs
            },
            'WASTE': {
                'waste_management': Decimal('0.50'),  # 50% reduction in waste
                'maintenance_savings': Decimal('0.05'),  # 5% reduction in maintenance costs
            }
        }

    def calculate_roi(self, implementation_cost, annual_savings, years=10):
        """Calculate ROI over specified years"""
        total_savings = annual_savings * years
        roi = ((total_savings - implementation_cost) / implementation_cost) * 100
        return roi

    def calculate_npv(self, implementation_cost, annual_savings, years=10):
        """Calculate Net Present Value"""
        npv = -implementation_cost
        for year in range(1, years + 1):
            npv += annual_savings / (1 + self.DISCOUNT_RATE) ** year
        return npv

    def calculate_payback_period(self, implementation_cost, annual_savings):
        """Calculate payback period in years"""
        if annual_savings <= 0:
            return float('inf')
        return implementation_cost / annual_savings

    def calculate_carbon_credits(self, emission_reduction):
        """Calculate potential carbon credit value"""
        return emission_reduction * self.CARBON_CREDIT_PRICE

    def project_costs(self, current_cost, years=10):
        """Project costs with inflation"""
        projected_costs = []
        for year in range(years):
            cost = current_cost * (1 + self.INFLATION_RATE) ** year
            projected_costs.append(cost)
        return projected_costs

    def calculate_intervention_impact(self, intervention_type, current_emissions, implementation_cost, 
                                   annual_maintenance, electricity_consumption=0):
        """Calculate comprehensive impact of an intervention"""
        effectiveness = self.EFFECTIVENESS.get(intervention_type, {})
        
        # Calculate emission reductions
        emission_reduction = Decimal('0')
        for emission_type, reduction_rate in effectiveness.items():
            if emission_type in current_emissions:
                emission_reduction += current_emissions[emission_type] * reduction_rate

        # Calculate financial savings
        energy_savings = Decimal('0')
        if 'grid_electricity' in effectiveness:
            energy_savings = electricity_consumption * effectiveness['grid_electricity'] * self.ELECTRICITY_COST

        maintenance_savings = Decimal('0')
        if 'maintenance_savings' in effectiveness:
            maintenance_savings = annual_maintenance * effectiveness['maintenance_savings']

        annual_savings = energy_savings + maintenance_savings

        # Calculate carbon credits
        carbon_credits = self.calculate_carbon_credits(emission_reduction)

        # Calculate ROI and NPV
        roi = self.calculate_roi(implementation_cost, annual_savings)
        npv = self.calculate_npv(implementation_cost, annual_savings)
        payback_period = self.calculate_payback_period(implementation_cost, annual_savings)

        # Project costs over time
        projected_savings = self.project_costs(annual_savings)
        
        return {
            'emission_reduction': emission_reduction,
            'annual_savings': annual_savings,
            'carbon_credits': carbon_credits,
            'roi': roi,
            'npv': npv,
            'payback_period': payback_period,
            'projected_savings': projected_savings,
            'energy_savings': energy_savings,
            'maintenance_savings': maintenance_savings
        }

class EnvironmentalImpactAnalyzer:
    def __init__(self):
        # Environmental impact factors
        self.IMPACT_FACTORS = {
            'grid_electricity': {
                'co2_per_unit': Decimal('0.5'),  # kg CO2 per kWh
                'water_per_unit': Decimal('1.5'),  # liters per kWh
                'trees_equivalent': Decimal('0.017')  # trees needed per kg CO2
            },
            'waste_management': {
                'co2_per_unit': Decimal('2.5'),  # kg CO2 per kg waste
                'groundwater_impact': Decimal('0.1'),  # groundwater impact score per kg
                'land_use': Decimal('0.05')  # m² per kg waste
            }
        }

    def calculate_environmental_impact(self, emission_type, amount):
        """Calculate environmental impact metrics"""
        impact_factors = self.IMPACT_FACTORS.get(emission_type, {})
        
        impact = {
            'co2_emissions': amount * impact_factors.get('co2_per_unit', Decimal('0')),
            'water_impact': amount * impact_factors.get('water_per_unit', Decimal('0')),
            'trees_needed': amount * impact_factors.get('trees_equivalent', Decimal('0')),
            'groundwater_impact': amount * impact_factors.get('groundwater_impact', Decimal('0')),
            'land_use': amount * impact_factors.get('land_use', Decimal('0'))
        }
        
        return impact

class PolicyImpactAnalyzer:
    def __init__(self):
        self.SDG_WEIGHTS = {
            'SOLAR': {
                'sdg7_clean_energy': Decimal('0.8'),
                'sdg13_climate_action': Decimal('0.7'),
                'sdg11_sustainable_cities': Decimal('0.6')
            },
            'WASTE': {
                'sdg12_responsible_consumption': Decimal('0.8'),
                'sdg11_sustainable_cities': Decimal('0.7'),
                'sdg3_good_health': Decimal('0.6')
            }
        }
        
        self.POLICY_ALIGNMENT_SCORES = {
            'carbon_tax_readiness': Decimal('0.8'),
            'green_funding_eligibility': Decimal('0.7'),
            'regulatory_compliance': Decimal('0.9')
        }

    def calculate_sdg_impact(self, intervention_type, emission_reduction):
        """Calculate impact on Sustainable Development Goals"""
        weights = self.SDG_WEIGHTS.get(intervention_type, {})
        
        sdg_impact = {}
        for sdg, weight in weights.items():
            sdg_impact[sdg] = emission_reduction * weight
            
        return sdg_impact

    def calculate_policy_alignment(self, intervention_type, investment_size):
        """Calculate alignment with policy objectives"""
        alignment_scores = {}
        for policy, base_score in self.POLICY_ALIGNMENT_SCORES.items():
            # Adjust score based on investment size
            size_factor = (investment_size / Decimal('1000000')).min(Decimal('1'))  # Cap at 1
            alignment_scores[policy] = base_score * (Decimal('1') + size_factor)
            
        return alignment_scores
