class StatsAnalyzer:
    @staticmethod
    def compare_users(u1_data, u2_data):
        # Добавили Rank и Level
        metrics = {
            'OverallPP': 'PP',
            'OverallAccuracy': 'Accuracy',
            'GlobalRank': 'Rank',
            'OverallPlaycount': 'Playcount',
            'Level': 'Level'
        }
        results = {}

        for key, name in metrics.items():
            val1 = u1_data.get(key, 0)
            val2 = u2_data.get(key, 0)
            
            # Логика определения победителя
            if key == 'GlobalRank':
                # Ранг 1 лучше чем ранг 100
                winner = 1 if val1 < val2 else 2
            else:
                winner = 1 if val1 > val2 else 2
                
            results[key] = {
                'name': name,
                'u1': val1,
                'u2': val2,
                'winner': winner
            }
        
        return results