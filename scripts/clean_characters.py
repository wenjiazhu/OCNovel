import json
import re
from opencc import OpenCC

def load_characters(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_characters(characters, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(characters, f, ensure_ascii=False, indent=2)

def is_emotion_or_state(text):
    emotion_keywords = {
        '焦急', '愤怒', '恐惧', '噩梦', '惊醒', '战栗', '懵逼', '疑惑', '警惕',
        '绝望', '希冀', '无力感', '窘迫', '心虚', '祈祷', '震惊', '惊喜',
        '坚定', '果敢', '狂喜', '紧张', '严肃', '凝重', '大胆', '疯狂', '悲壮',
        '决绝', '腹诽', '怒火', '欣喜', '惊訝', '审视', '沉着', '认真',
        '担忧', '惊恐', '颤抖', '不安', '迷茫', '混乱', '激动', '急迫', '悠闲',
        '老练', '意外', '威慑', '好奇', '放松', '专注', '精明'
    }
    
    state_keywords = {
        '伤痕累累', '疲惫', '灼伤', '虎口发麻', '虚脱', '煞白', '僵硬',
        '满头大汗', '酸胀', '通红', '青筋暴起', '麻木', '失去知觉',
        '灵力枯竭', '重伤', '透支', '反噬', '头晕眼花', '苍白', '溢血',
        '丹田空虚', '瘫软', '极限', '崩溃', '刺痛', '紧绷', '发烫',
        '浑身不自在', '视线模糊', '气喘吁吁', '动作迟缓', '语气不安',
        '沉默不语', '声音嘶哑', '浸湿', '颤抖', '喘粗气'
    }
    
    description_keywords = {
        '劫后余生', '做梦', '初次登场', '意外成名', '威慑', '绘声绘色',
        '陷入', '眼神', '语气', '声音', '动作', '表情', '长长地', '微微',
        '突然', '猛地', '缓慢', '轻柔', '全神贯注', '置若罔闻'
    }
    
    return any(keyword in text for keyword in emotion_keywords | state_keywords | description_keywords)

def is_valid_development_stage(text):
    valid_stages = {
        '初次登场', '崭露头角', '初露锋芒', '声名鹊起', '威震一方',
        '名震天下', '巅峰时期', '陨落', '重生', '涅槃重生'
    }
    return text in valid_stages

def is_valid_realm(text):
    valid_realms = {
        '凡人', '练气', '筑基', '金丹', '元婴', '化神', '炼虚', '合体', '大乘',
        '散修', '武者', '武师', '武宗', '武王', '武皇', '武帝', '武圣',
        '人仙', '地仙', '天仙', '金仙', '太乙', '大罗'
    }
    return text in valid_realms

def clean_field(text, field_name):
    if not isinstance(text, str):
        return "凡人" if field_name == "realm" else "初次登场"
        
    states = [s.strip() for s in text.split(',')]
    
    # 收集描述性文本作为历史记录
    descriptions = [s for s in states if s and is_emotion_or_state(s)]
    
    # 根据字段类型过滤有效值
    if field_name == 'development_stage':
        valid_states = [s for s in states if is_valid_development_stage(s)]
        return valid_states[0] if valid_states else "初次登场"
    else:  # realm
        valid_states = [s for s in states if is_valid_realm(s)]
        return valid_states[0] if valid_states else "凡人"
    
    return descriptions

def convert_to_simplified(text):
    cc = OpenCC('t2s')
    return cc.convert(text)

def merge_duplicate_characters(characters):
    # 创建简繁体转换器
    cc = OpenCC('t2s')
    
    # 创建映射存储相似名称的角色
    similar_names = {}
    
    # 查找相似的名称
    for name in characters.keys():
        # 转换为简体并移除非中文字符
        simplified_name = cc.convert(name)
        normalized_name = re.sub(r'[^\u4e00-\u9fff]', '', simplified_name)
        
        if normalized_name not in similar_names:
            similar_names[normalized_name] = []
        similar_names[normalized_name].append(name)
    
    # 合并相似的角色
    merged_characters = {}
    for normalized_name, variants in similar_names.items():
        if len(variants) > 1:
            # 使用简体中文名称作为主要名称
            main_name = cc.convert(variants[0])
            main_char = characters[variants[0]].copy()
            main_char['name'] = main_name  # 更新角色名为简体
            
            # 记录情感、状态和描述历史
            emotions_history = set()
            states_history = set()
            descriptions_history = set()
            
            # 合并所有变体的信息
            for variant in variants:
                var_char = characters[variant]
                
                # 收集历史情感、状态和描述
                if 'development_stage' in var_char:
                    text_parts = [s.strip() for s in var_char['development_stage'].split(',')]
                    for part in text_parts:
                        if is_emotion_or_state(part):
                            if any(keyword in part for keyword in {'担忧', '惊恐', '愤怒', '喜悦', '恐惧'}):
                                emotions_history.add(part)
                            elif any(keyword in part for keyword in {'疲惫', '虚脱', '重伤', '麻木'}):
                                states_history.add(part)
                            else:
                                descriptions_history.add(part)
                
                if 'realm' in var_char:
                    text_parts = [s.strip() for s in var_char['realm'].split(',')]
                    for part in text_parts:
                        if is_emotion_or_state(part):
                            if any(keyword in part for keyword in {'担忧', '惊恐', '愤怒', '喜悦', '恐惧'}):
                                emotions_history.add(part)
                            elif any(keyword in part for keyword in {'疲惫', '虚脱', '重伤', '麻木'}):
                                states_history.add(part)
                            else:
                                descriptions_history.add(part)
            
            # 添加历史记录
            if emotions_history:
                main_char['emotions_history'] = list(emotions_history)
            if states_history:
                main_char['states_history'] = list(states_history)
            if descriptions_history:
                main_char['descriptions_history'] = list(descriptions_history)
            
            # 清理主要字段
            main_char['development_stage'] = clean_field(main_char.get('development_stage', '初次登场'), 'development_stage')
            main_char['realm'] = clean_field(main_char.get('realm', '凡人'), 'realm')
            
            merged_characters[main_name] = main_char
        else:
            # 单个角色也需要清理和转换为简体
            name = cc.convert(variants[0])
            char = characters[variants[0]].copy()
            char['name'] = name
            
            # 收集并清理情感、状态和描述历史
            emotions_history = set()
            states_history = set()
            descriptions_history = set()
            
            # 处理development_stage
            if 'development_stage' in char:
                text_parts = [s.strip() for s in char['development_stage'].split(',')]
                for part in text_parts:
                    if is_emotion_or_state(part):
                        if any(keyword in part for keyword in {'担忧', '惊恐', '愤怒', '喜悦', '恐惧'}):
                            emotions_history.add(part)
                        elif any(keyword in part for keyword in {'疲惫', '虚脱', '重伤', '麻木'}):
                            states_history.add(part)
                        else:
                            descriptions_history.add(part)
            
            # 处理realm
            if 'realm' in char:
                text_parts = [s.strip() for s in char['realm'].split(',')]
                for part in text_parts:
                    if is_emotion_or_state(part):
                        if any(keyword in part for keyword in {'担忧', '惊恐', '愤怒', '喜悦', '恐惧'}):
                            emotions_history.add(part)
                        elif any(keyword in part for keyword in {'疲惫', '虚脱', '重伤', '麻木'}):
                            states_history.add(part)
                        else:
                            descriptions_history.add(part)
            
            # 添加历史记录
            if emotions_history:
                char['emotions_history'] = list(emotions_history)
            if states_history:
                char['states_history'] = list(states_history)
            if descriptions_history:
                char['descriptions_history'] = list(descriptions_history)
            
            # 清理主要字段
            char['development_stage'] = clean_field(char.get('development_stage', '初次登场'), 'development_stage')
            char['realm'] = clean_field(char.get('realm', '凡人'), 'realm')
            
            merged_characters[name] = char
    
    return merged_characters

def main():
    # 读取配置文件
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    output_dir = config['output_config']['output_dir']
    input_file = f'{output_dir}/characters.json'
    output_file = f'{output_dir}/characters_cleaned.json'
    
    # 加载并清理角色库
    characters = load_characters(input_file)
    cleaned_characters = merge_duplicate_characters(characters)
    
    # 保存清理后的角色库
    save_characters(cleaned_characters, output_file)
    print(f'已完成角色库清理，结果保存至：{output_file}')

if __name__ == '__main__':
    main()